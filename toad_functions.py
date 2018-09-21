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
from enum import Enum
from sendgrid.helpers.mail import Email, Mail, Content
from datetime import datetime
from datetime import timezone
from datetime import timedelta

import re

_DATE_REGEX = r'.*((\d{4}-\d{2}-\d{2}-\d{6})(Z|[+-]\d+)?)-(.*)\.([a-zA-Z0-9]+)'

class SensorState(Enum):
    IDLE = 0
    PAUSED = 1
    ACTIVATED = 2
    PAUSED_ACTIVATED = 3

    def is_activated(self):
        return self == SensorState.IDLE or self == SensorState.ACTIVATED

    def activate(self):
        if self == SensorState.PAUSED or self == SensorState.PAUSED_ACTIVATED:
            return SensorState.PAUSED_ACTIVATED 
        else:
            return SensorState.ACTIVATED

# Get semantic information from a file in tuple format
# datetime([0] yyyy, [1] MM, [2], dd, [3], HH, [4] MM, [5] SS), [6] sensorXX
def parseFileInfo(filename, fallback):
    if fallback is None:
        raise TypeError("A fallback must be provided")
    match = re.search(_DATE_REGEX, filename)
    if match == None:
        raise ValueError("Filename invalid, cannot parse date")
    date = parser.isoparse(match[1])
    if date.tzinfo == None:
        offset = tzoffset(None, fallback)
        date = date.replace(tzinfo=offset)
    return (date, match[4])

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

def getNotificationsAndActivatingSensors(dropbox_files, file_history,
    sensor_history, pause_duration, fallback_utc_offset, datetime_now):
    # Array of tuples to store results of the upcoming search
    notifications_to_send = []
    sensors_status = {}

    # first let us build up the current state of the sensors
    for sensor_name in sensor_history:
        previous_fire = parser.isoparse(sensor_history[sensor_name])
        assert previous_fire.tzinfo != None, "Corrupt sensors.json, a date is missing it's UTC offset"
        # how long between the last sensor fire and now
        elapsed_time = datetime_now - previous_fire
        (quotient, _remainder) = divmod(elapsed_time.total_seconds(), pause_duration)
        # keep sensors still within timeout window paused, otherwise set state to idle
        sensors_status[sensor_name] = SensorState.IDLE if quotient >= 1 else SensorState.PAUSED

    # Check for new records by comparing against what we already have
    for entry in dropbox_files:
        filename = entry.name
        if filename not in file_history or file_history[filename] == False:
            try:
                # Extract semantic info from name for easy processing
                (recorded_at, sensor_name) = parseFileInfo(filename, fallback_utc_offset)
            except Exception as e:
                print(f"Could not process file name {filename}: " + str(e))
                continue # Malformed filename, don't worry about it

            # Append notification regardless of whether or not any sensor will trigger an email
            notifications_to_send.append((entry, recorded_at, sensor_name))
            # Have we seen this sensor before?
            if sensor_name in sensor_history:
                # This used to be: how long between recorded date and previous 
                # sensor fire:
                #elapsed_time = recorded_at - previous_fire
                # But what we really want to know is how long since the last
                # sensor fire and now? Which is taken care of above.
                # Once we know that it is simply a case of reporting any
                # files that have not been repported yet.
                sensors_status[sensor_name] = sensors_status[sensor_name].activate()              
            else:
                # Brand new sensor, add it to the list
                sensors_status[sensor_name] = SensorState.ACTIVATED
 
    return (notifications_to_send, sensors_status)

def updateState(notifications_to_send, sensors_status, file_history, sensor_history, datetime_now):
    for (sensor_name, state) in sensors_status.items():
        # Update state for this sensor
        # For IDLE and PAUSE do nothing. 
        # For ACTIVATED store date to start a pause.
        # For ACTIVATED_PAUSED we don't reset the pause timer so do nothing also.
        if state == SensorState.ACTIVATED:
            sensor_history[sensor_name] = datetime_now.isoformat()

    # Record whether each notification should be dispatched 
    # If *any* sensor has ACTIVATED (not on a timeout ACTIVATED_PAUSED):
    #     then send all notifications
    # The following case should not happen:
    #   If *all* sensors are IDLE and there are pending notifications
    # In other combinations of IDLE/PAUSED/ACTIVATED_PAUSED we do NOT send 
    # notifications.
    any_activation = any(v == SensorState.ACTIVATED for (k,v) in sensors_status.items())
    
    all_idle = all((v == SensorState.IDLE for (k,v) in sensors_status.items()))
    assert (not all_idle or len(notifications_to_send) == 0), "All sensors are IDLE but there are pending notifications!"
    
    send_notifications = any_activation #or all_idle
    for (entry, *_) in notifications_to_send:
        file_history[entry.name] = send_notifications

    # Return the updated state
    return (file_history, sensor_history, send_notifications)

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

def formatNotifications(notifications_to_send, sensors_status, href_function):
    # Group notifications by sensor and send a bundled email now.
    email_body = "<h1>Toad Update in Dropbox</h1>"
    for (sensor_name, state) in sensors_status.items():
        # send notification for either ACTIVATED or PAUSED_ACTIVATED
        if not state.is_activated():
            continue

        # Process for this sensor
        sensor_header = f"<h2>Suspicious recordings from { sensor_name }</h2>"
        header_added = False
        for notification in notifications_to_send:
            (entry, _recorded_at, notification_sensor) = notification
            if sensor_name != notification_sensor:
                continue

            if not header_added:
                email_body += sensor_header
                header_added = True
            
            # get the drop box file name, get the path_lower to use for get_temporary_link
            filename = entry.name
            db_path = entry.path_lower
            db_href = href_function(db_path) 
            
            # Add the file to the email
            email_body = email_body + f"<p><a href=\"{db_href}\">{filename}</a></p>"
    return email_body

# Function to send notifications
# body is the content of the email, send_to_emails is the array of emails to send to, send_from is the address to send from, sg is a SendGrid object
# returns true if everything worked.
def sendEmail(body, instance_name, send_to_emails, send_from, sg):
    # We assume this function is only called if notifications should be sent.
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
                    Sent from { instance_name } ({ host })
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
    print("Notification sent to subscribers was " + ("successful" if completed_well else "not successful") )
    return completed_well