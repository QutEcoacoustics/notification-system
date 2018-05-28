# Import libraries
import os
import sys
import json
import requests
import datetime
import dropbox
import sendgrid
from dateutil import parser
from toad_functions import *
from sendgrid.helpers.mail import *

# Load configuration
config_path = "./config.json"
if len(sys.argv) >= 2:
    config_path = sys.argv[1]
system_configuration = json.loads(open(config_path, "r").read())
bot_address = system_configuration['send_from']

# Open files
file_history_io = open("files.json", "r")
sensor_history_io = open("sensors.json", "r")

# Load state databases from text file
file_history = json.loads(file_history_io.read())
sensor_history = json.loads(sensor_history_io.read())

# Close files
file_history_io.close();
sensor_history_io.close();

# Authenticate
sg = sendgrid.SendGridAPIClient(apikey=system_configuration['sendgrid_api_key'])
dbx = dropbox.Dropbox(system_configuration['dropbox_api_key'])
dbx.users_get_current_account()

# Pull list of files in Dropbox
dropbox_files = getFilesFromDropbox(dbx, root_folder=system_configuration['root_folder'])
dropbox_file_names = [entry.name for entry in dropbox_files]

# Get list of emails to send to by scanning Dropbox
send_to_emails = getEmailsFromDropbox(system_configuration["filename_send_to"], dbx, debug=False)

# Search for new notifications, in the context of file and sensor history
pause_duration = int(system_configuration["pause_duration"])
(notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(dropbox_file_names, file_history, sensor_history, pause_duration)

# Update state
(file_history, sensor_history) = updateState(notifications_to_send, activated_sensors, file_history, sensor_history)
file_history_io = open("files.json", "w")
sensor_history_io = open("sensors.json", "w")
json.dump(file_history, file_history_io)
json.dump(sensor_history, sensor_history_io)
file_history_io.close();
sensor_history_io.close();

# Send Notifications
sendNotifications(dropbox_files, notifications_to_send, activated_sensors, send_to_emails, bot_address, sg, dbx, debug=False)

# Done
print("Script finished")