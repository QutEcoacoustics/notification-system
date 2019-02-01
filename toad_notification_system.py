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
root_folder = system_configuration['root_folder']
dropbox_files = toad_functions.getFilesFromDropbox(dbx, root_folder=root_folder)

# Get list of emails to send to by scanning Dropbox
send_to_emails = toad_functions.getEmailsFromDropbox(system_configuration["filename_send_to"], dbx, debug=False)

# Search for new notifications, in the context of file and sensor history
now = datetime.now(timezone.utc)
pause_duration = system_configuration["pause_duration"]
fallback_utc_offset = timedelta(seconds=(system_configuration["fallback_utc_offset"]))
(notifications_to_send, sensors_status) = toad_functions.getNotificationsAndActivatingSensors(
    dropbox_files,file_history, sensor_history, pause_duration, fallback_utc_offset, now)

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
instance_name = system_configuration["name"]
if send_notifications:
    href_function = lambda path: toad_functions.getSharedLink(dbx, path)
    body = toad_functions.formatNotifications(notifications_to_send, sensors_status, href_function)
    toad_functions.sendEmail(body, instance_name, send_to_emails, bot_address, sg)

print("Updating sensor health")

# get a list of sensor folders
status_path = system_configuration["log_folder"]
update_at = system_configuration["update_status_report_at"]
status_save_path = system_configuration["save_status_reports_folder"] or system_configuration["log_folder"]

if status_path:
    if update_at and toad_functions.closeToTimeOfDay(now, update_at):
        all_files = toad_functions.getFilesFromDropbox(dbx, root_folder=status_path)
        log_dirs = toad_functions.filterSensorDirs(all_files, [root_folder])
        # for each log dir, get logs
        # Note: this would be an optimal async operation
        # Note: we could run into API limitations here
        limit = None # no limit, or you could set one timedelta(days=3)
        all_sensors  = {}
        for (log_dir, sensor) in log_dirs:
            print("Downloading logs for " + log_dir)
            log_files = toad_functions.getFilesFromDropbox(dbx, root_folder=log_dir)
            report = toad_functions.filterGroupLogFiles(log_files, now, limit, fallback_utc_offset)
            last_activation = None if new_instance else sensor_history.get(sensor)
            all_sensors[sensor] = {"logs": report, "last_activation":  last_activation}

        full_report = {"sensors": all_sensors, "report_date": now.isoformat(), "name": instance_name}
        # upload the report to dropbox
        content = json.dumps(full_report)
        
        report_path = status_save_path + "/sensors_status.json"
        print("Uploading report to " + report_path)
        toad_functions.uploadFileToDropbox(dbx, content, report_path)

        # upload the html report viewer
        target_date = now.date()
        report_path = status_save_path + f"/sensors_status_{target_date.isoformat()}.html"
        print("Uploading template to " + report_path)
        with open("sensors_status.template.html", 'r', encoding = 'utf-8') as f:
            viewer_template = f.read()
            
            report = toad_functions.templateReport(viewer_template, full_report, target_date)
            toad_functions.uploadFileToDropbox(dbx, report, report_path)
    else:
        print("skipping status update, not close enough to update_status_report_at times")
else:
    print("Skipping status update, no log_folder set in config file")

# Done
print("Script finished")