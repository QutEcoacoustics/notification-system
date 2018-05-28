# Import libraries
import os
import json
import requests
import datetime
import dropbox
import sendgrid
from dateutil import parser
from sendgrid.helpers.mail import *
from datetime import datetime

# Get semantic information from a file in tuple format
# datetime([0] yyyy, [1] MM, [2], dd, [3], HH, [4] MM, [5] SS), [6] sensorXX
def parseFileInfo(filename):
    data = [x.strip() for x in filename.split('-')]
    return (datetime(int(data[1]), int(data[2]), int(data[3]), int(data[4][:2]), int(data[4][2:-2]), int(data[4][-2:])), data[5][:-5])

# Function to send notifications
# body is the content of the email, send_to_emails is the array of emails to send to, send_from is the address to send from, sg is a SendGrid object
# returns true if everything worked.
def sendEmail(body, send_to_emails, send_from, sg):
    completed_well = False
    # Send emails
    for recipient in send_to_emails:
        # Prepare the email
        from_email = Email(send_from)
        to_email = Email(recipient)
        subject = 'Suspicious Recordings from Sensors'
        # Email Copy
        email_html_copy = """
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml">
         <head>
          <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
          <title>""" + subject + """</title>
          <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
         </head><body>""" + body + """</body>
        </html>
        """
        content = Content("text/html", body)
        mail = Mail(from_email, subject, to_email, content)
        # Send the email
        response = sg.client.mail.send.post(request_body=mail.get())
        # Check the response and return true if success (any HTTP code starting with 2)
        if str(response.status_code).startswith('2'):
            completed_well = True
            break
    # Indicate whether everything worked as expected
    return completed_well

# iteratively pull list of files in Dropbox
def getFilesFromDropbox(dbx, root_folder=''):
    dropbox_files = []
    finished_looping = False
    fetched_files = dbx.files_list_folder(root_folder)
    while (not finished_looping):
        for entry in fetched_files.entries:
            dropbox_files.append(entry)
        if fetched_files.has_more:
            fetched_files = dbx.files_list_folder_continue(fetched_files.cursor).entries
        else:
            finished_looping = True
    return dropbox_files

def getEmailsFromDropbox(email_config_file_path, dbx, debug=False, debug_content="", debug_files=""):
    send_to_emails = []
    if not debug:
        # This is the file that contains the emails to send to
        temp_file = "./emails_to_send_to.txt"

        # Download file from dropbox
        dbx.files_download_to_file(temp_file, email_config_file_path)
        
        email_file_data = open(temp_file, "r").read()
        # Pull the email data out
        send_to_emails = [x.strip() for x in email_file_data.split('\n')]
    else:
        # Same as above but with debugging workflow
        for entry in debug_files:
            if email_config_file_path in entry:
                email_file_data = debug_content
                send_to_emails = [x.strip() for x in email_file_data.split('\n')]
                break
    return send_to_emails

def getNotificationsAndActivatingSensors(dropbox_file_names, file_history, sensor_history, pause_duration):
    # Array of tuples to store results of the upcoming search
    notifications_to_send = []
    activated_sensors = []
    # Check for new records by comparing against what we already have
    for entry in dropbox_file_names:
        if entry not in file_history or file_history[entry] == False:
            try:
                # Extract semantic info from name for easy processing
                (recorded_at, sensor) = parseFileInfo(entry)
                # Append notification regardless of whether or not any sensor will trigger an email
                notifications_to_send.append((entry, recorded_at, sensor))
                # Have we seen this sensor before?
                if sensor in sensor_history:
                    previous_fire = parser.parse(sensor_history[sensor])
                    elapsed_time = recorded_at - previous_fire
                    (hours, remainder) = divmod(elapsed_time.total_seconds(), pause_duration)
                    if hours >= 1:
                        # If the sensor has already fired within the last hour, don't notify yet - we'll catch it in the future
                        # Otherwise, append it to the list to the list to ensure we send a bundled notification now
                        if not sensor in activated_sensors:
                            activated_sensors.append(sensor)
                else:
                    # Brand new sensor, add it to the list
                    if not sensor in activated_sensors:
                        activated_sensors.append(sensor)
            except:
                pass # Malformed filename, don't worry about it
    return (notifications_to_send, activated_sensors)

def updateState(notifications_to_send, activated_sensors, file_history, sensor_history):
    for sensor in activated_sensors:
        # Update state for this sensor
        sensor_history[sensor] = str(datetime.now())
    # We're only updating files if a notification was sent
    if len(activated_sensors) > 0:
        for notification in notifications_to_send:
            (filename, recorded_at, _sensor) = notification
            file_history[filename] = True
    # Return the updated state
    return (file_history, sensor_history)

def sendNotifications(dropbox_files, notifications_to_send, activated_sensors, send_to_emails, send_from, sg, dbx, debug=False):
    # If we have activated sensors, group notifications by sensor and send a bundled email now
    if len(activated_sensors) > 0:
        email_body = "<h1>Toad Update in Dropbox</h1>"
        for sensor in activated_sensors:
            # Process for this sensor
            email_body = email_body + "<h2>Suspicious recordings from " + sensor + "</h2>"
            for notification in notifications_to_send:
                (filename, recorded_at, _sensor) = notification
                # find the drop box file name, get the path_lower to use for get_temporary_link
                for entry in dropbox_files:
                    if filename in entry.name:
                        db_path = entry.path_lower
                        break

                if sensor == _sensor:
                    # Add the file to the email
                    email_body = email_body + "<p><a href=\"" + dbx.files_get_temporary_link(db_path).link + "\">" + filename + "</a></p>"
        # Send the group notification
        if (not debug):
            sendEmail(email_body, send_to_emails, send_from, sg)
        print(send_to_emails)
        print("Notification sent to subscribers")
        return True
    else:
        return False
