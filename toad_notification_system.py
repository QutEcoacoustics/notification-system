# Import libraries
import os
import sys
import json
import requests
import datetime
from datetime import datetime
from datetime import timezone
from dateutil import parser
from datetime import timedelta
import dropbox
import sendgrid
import toad_functions

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
dropbox_files = toad_functions.getFilesFromDropbox(dbx, root_folder=system_configuration['root_folder'])
dropbox_file_names = [entry.name for entry in dropbox_files]

# Get list of emails to send to by scanning Dropbox
send_to_emails = toad_functions.getEmailsFromDropbox(system_configuration["filename_send_to"], dbx, debug=False)

# Search for new notifications, in the context of file and sensor history
now = datetime.now(timezone.utc)
pause_duration = system_configuration["pause_duration"]
fallback_utc_offset = timedelta(seconds=(system_configuration["fallback_utc_offset"]))
(notifications_to_send, sensors_status) = toad_functions.getNotificationsAndActivatingSensors(dropbox_file_names, file_history,
    sensor_history, pause_duration, fallback_utc_offset, now)

# in a new instance, when there are no history files available (files.json and sensors.json)
# we modify the sensor activation date to now - pause_duration. This way we alert
# for any files in the next block, but for none of the previous files
if new_instance:
    print("New instance detected. Sensor activation date is shifted back " + str(pause_duration))
    activation_adjustment = -1 * pause_duration
    # Activation adjustment allows us to tweak when a sensor was activated.
    # Useful for new deploys without past history files available.
    now = now + timedelta(seconds=activation_adjustment)

# Update state
(file_history, sensor_history, send_notifications) = toad_functions.updateState(notifications_to_send, sensors_status, file_history, sensor_history, now)
file_history_io = open("files.json", "w")
sensor_history_io = open("sensors.json", "w")
json.dump(file_history, file_history_io)
json.dump(sensor_history, sensor_history_io)
file_history_io.close()
sensor_history_io.close()

# Do not send notifications for new instance initial setup so we don't send a
#  notification for every previous file - this should only happen when there are
#  no history files available (files.json and sensors.json are empty).
if new_instance:
    print("New instance detected. Squashing all notifications. New notifications will work from next script run")
    send_notifications = False

# Send Notifications
if send_notifications:
    href_function = lambda path: toad_functions.getSharedLink(dbx, path)
    body = toad_functions.formatNotifications(notifications_to_send, sensors_status, href_function)
    toad_functions.sendEmail(body, send_to_emails, bot_address, sg)

# Done
print("Script finished")