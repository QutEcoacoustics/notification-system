# Import libraries
import os
import json
import requests
import datetime
import dropbox
import sendgrid
import platform
from dateutil import parser
from dateutil.tz import tzoffset
from sendgrid.helpers.mail import *
from datetime import datetime
from datetime import timezone
from datetime import timedelta

import re

DATE_REGEX = r'.*((\d{4}-\d{2}-\d{2}-\d{6})(Z|[+-]\d+)?)-(.*)\.([a-zA-Z0-9]+)'

# Get semantic information from a file in tuple format
# datetime([0] yyyy, [1] MM, [2], dd, [3], HH, [4] MM, [5] SS), [6] sensorXX
def parseFileInfo(filename, fallback):
    if fallback is None:
        raise TypeError("A fallback must be provided")
    match = re.search(DATE_REGEX, filename)
    if match == None:
        raise ValueError("Filename invalid, cannot parse date")
    date = parser.isoparse(match[1])
    if date.tzinfo == None:
        offset = tzoffset(None, fallback)
        date = date.replace(tzinfo=offset)
    return (date, match[4])

# Function to send notifications
# body is the content of the email, send_to_emails is the array of emails to send to, send_from is the address to send from, sg is a SendGrid object
# returns true if everything worked.
def sendEmail(body, send_to_emails, send_from, sg):
    completed_well = False
    host = platform.node() or "(unknown)"
    
    # Send emails
    for recipient in send_to_emails:
        # Prepare the email
        from_email = Email(send_from)
        to_email = Email(recipient)
        subject = 'Suspicious Recordings from Sensors'
        # Email Copy
        email_html_copy = f"""
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml">
         <head>
          <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
          <title> { subject } </title>
          <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
         </head>
         <body>
            { body }
            <br/>
            <br/>
            <br/>
            <p>
                <small style="font-size: 7pt;color:#ccc;">
                    Sent from { host }
                </small>
            </p>
        </body>
        </html>
        """
        content = Content("text/html", email_html_copy)
        mail = Mail(from_email, subject, to_email, content)
        # Send the email
        response = sg.client.mail.send.post(request_body=mail.get())
        # Check the response and return true if success (any HTTP code starting with 2)
        completed_well = str(response.status_code).startswith('2')
        print(f"email sent to '{recipient}' was { '' if completed_well else ' NOT '} successful")

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

def getNotificationsAndActivatingSensors(dropbox_file_names, file_history, sensor_history, pause_duration, fallback_utc_offset):
    # Array of tuples to store results of the upcoming search
    notifications_to_send = []
    activated_sensors = []

    # Check for new records by comparing against what we already have
    for entry in dropbox_file_names:
        if entry not in file_history or file_history[entry] == False:
            try:
                # Extract semantic info from name for easy processing
                (recorded_at, sensor) = parseFileInfo(entry, fallback_utc_offset)
            except Exception as e:
                print(f"Could not process file name {entry}: " + str(e))
                pass # Malformed filename, don't worry about it

            # Append notification regardless of whether or not any sensor will trigger an email
            notifications_to_send.append((entry, recorded_at, sensor))
            # Have we seen this sensor before?
            if sensor in sensor_history:
                previous_fire = parser.isoparse(sensor_history[sensor])
                assert previous_fire.tzinfo != None, "Corrupt sensors.json, a date is missing it's UTC offset"
                elapsed_time = recorded_at - previous_fire
                (quotient, remainder) = divmod(elapsed_time.total_seconds(), pause_duration)
                if quotient >= 1:
                    # If the sensor has already fired within the last hour, don't notify yet - we'll catch it in the future
                    # Otherwise, append it to the list to the list to ensure we send a bundled notification now
                    if not sensor in activated_sensors:
                        activated_sensors.append(sensor)
            else:
                # Brand new sensor, add it to the list
                if not sensor in activated_sensors:
                    activated_sensors.append(sensor)

    return (notifications_to_send, activated_sensors)

def updateState(notifications_to_send, activated_sensors, file_history, sensor_history, activation_adjustment = 0.0):
    for sensor in activated_sensors:
        # Update state for this sensor
        now = datetime.now(timezone.utc) + timedelta(seconds=activation_adjustment)
        sensor_history[sensor] = now.isoformat()
    # We're only updating files if a notification was sent
    if len(activated_sensors) > 0:
        for notification in notifications_to_send:
            (filename, recorded_at, _sensor) = notification
            file_history[filename] = True
    # Return the updated state
    return (file_history, sensor_history)

def getSharedLink(dbx, db_path):
    sharedLink = None
    try:
        # attempt to get a shared link - we can only do this once per path
        sharedLink = dbx.sharing_create_shared_link_with_settings(db_path)
    except dropbox.exceptions.ApiError as apiError:
        # if the error was a duplicate shared link
        if apiError.error.is_shared_link_already_exists():
            # then try and retrieve link.
            # we can only get all shared links for a path!
            # we assume the first one is valid, and that this app created it,
            #   and thus it has public accessibility!
            allLinks = dbx.sharing_get_shared_links(db_path).links
            sharedLink = allLinks[0]
            print("successfully retrieved existing shared link for " + db_path)
        else:
            raise
    return sharedLink.url

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
                    email_body = email_body + "<p><a href=\"" + getSharedLink(dbx, db_path) + "\">" + filename + "</a></p>"
        # Send the group notification
        if (not debug):
            success = sendEmail(email_body, send_to_emails, send_from, sg)
        print("Notification sent to subscribers was " + ("successful" if success else "not successful") )
        return True
    else:
        return False
