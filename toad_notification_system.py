# Import libraries
import os
import json
import requests
import datetime
import dropbox
import sendgrid
from dateutil import parser
from toad_functions import *
from sendgrid.helpers.mail import *

# Load configuration
system_configuration = json.loads(open("config.json", "r").read())
bot_address = system_configuration['send_from']

# Load state databases from text file
file_history = json.loads(open("files.json", "r").read())
sensor_history = json.loads(open("sensors.json", "r").read())

# Authenticate
sg = sendgrid.SendGridAPIClient(apikey=system_configuration['sendgrid_api_key'])
dbx = dropbox.Dropbox(system_configuration['dropbox_api_key'])
dbx.users_get_current_account()

# Pull list of files in Dropbox
dropbox_files = getFilesFromDropbox(dbx)

# Get list of emails to send to by scanning Dropbox
send_to_emails = getEmailsFromDropbox(dropbox_files, system_configuration["filename_send_to"], dbx, debug=False)

# Search for new notifications, in the context of file and sensor history
pause_duration = int(system_configuration["pause_duration"])
(notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors([entry.name for entry in dropbox_files], file_history, sensor_history, pause_duration)

# Send Notifications
sendNotifications(notifications_to_send, activated_sensors, send_to_emails, bot_address, sg, debug=False)

# Done
print("Script finished")