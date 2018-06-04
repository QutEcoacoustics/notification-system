# Import libraries
import os
import sys
import json
import requests
import datetime
import dropbox
import sendgrid
from dateutil import parser
from datetime import timedelta
from toad_functions import *
from sendgrid.helpers.mail import *

# Load configuration
config_path = "./config.json"
if len(sys.argv) >= 2:
    config_path = sys.argv[1]
system_configuration = json.loads(open(config_path, "r").read())
bot_address = system_configuration['send_from']

# Open files
# If the file does not exist, just feed the JSON parser and empty JSON object
new_instance = False
try:
    file_history_io = open("files.json", "r")
    file_history_text = file_history_io.read()
    file_history_io.close()
except:
    file_history_text = "{}"
    # we need to cater for empty file/sensor histories - indicative of a new
    # monitor being set up for an established folder
    new_instance = True

try:
    sensor_history_io = open("sensors.json", "r")
    sensor_history_text = sensor_history_io.read()
    sensor_history_io.close()
except:
    sensor_history_text =  "{}"

# Load state databases from text file
file_history = json.loads(file_history_text)
sensor_history = json.loads(sensor_history_text)

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
pause_duration = system_configuration["pause_duration"]
fallback_utc_offset = timedelta(seconds=(system_configuration["fallback_utc_offset"]))
(notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(dropbox_file_names, file_history, sensor_history, pause_duration, fallback_utc_offset)

# in a new instance, when there are no history files available (files.json and sensors.json)
# we modify the sensor activation date to now - pause_duration
activation_adjustment = 0.0
if new_instance:
    print("New instance detected. Sensor activation date is shifted back " + str(pause_duration))
    activation_adjustment = -1 * pause_duration

# Update state
(file_history, sensor_history) = updateState(notifications_to_send, activated_sensors, file_history, sensor_history, activation_adjustment)
file_history_io = open("files.json", "w")
sensor_history_io = open("sensors.json", "w")
json.dump(file_history, file_history_io)
json.dump(sensor_history, sensor_history_io)
file_history_io.close()
sensor_history_io.close()

# wipe out all activated sensors for and notification for new instance initial setup
# so we don't send a notification for every previous file - this should only happen
# when there are no history files available (files.json and sensors.json)
if new_instance:
    print("New instance detected. Squashing all notifications. New notifications will work from next script run")
    activated_sensors = []
    notifications_to_send = []

# Send Notifications
sendNotifications(dropbox_files, notifications_to_send, activated_sensors, send_to_emails, bot_address, sg, dbx, debug=False)

# Done
print("Script finished")