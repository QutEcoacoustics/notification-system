# notification-system
A simple python and cron combination to send alerts when files are added to a dropbox folder


[![Build Status](https://travis-ci.org/QutEcoacoustics/notification-system.svg?branch=master)](https://travis-ci.org/QutEcoacoustics/notification-system)
[![](https://images.microbadger.com/badges/version/qutecoacoustics/notification-system.svg)](https://microbadger.com/images/qutecoacoustics/notification-system "Get your own version badge on microbadger.com")


## Development

1. Requires Python 3.5 or above.
  - `apt-get install python3`
  - `apt-get install python3-pip`
1. Requires pipenv:
  `pip install pipenv`
1. Clone the repo
1. `pipenv install`
1. Start the pipenv shell
  - `pipenv shell`
1. Run the unit tests: `python unit_testing.py`

## Production

- Install docker
- Build Docker image: `docker build . -t qutecoacoustics/notification-system:latest`
- Define the path to your properly configured config directory:
  ` NS_CONFIG=$(pwd)`
- Run the Docker image: `docker run --mount "type=bind,source=$NS_CONFIG,destination=/config" qutecoacoustics/notification-system:latest`

## Config

Place a `config.json` file alongside `toad_functions.py` etc with the following format:
```
{
  "sendgrid_api_key": "<place your key here>",
  "dropbox_api_key": "<place your key here>",
  "send_from": "\"<project name>\" <email@example.com>",
  // the path to the file in dropbox containing the receiver list
  "filename_send_to": "email_alert_list.txt",
  "pause_duration": 3600,
  // An array of (time start, time end) tuples for allowed notification times
  // The  default if omitted is `[["00:00", "24:00"]]`.
  // The times are interpreted against the local time of the matched file,
  // parsed from it's filename.
  "whitelist_times_of_day" : [ ["20:00", "24:00"], ["00:00", "04:00"]],
  // If no utc offset found in filename, then assume this utc offset (in seconds)
  // e.g. 36000 for +10:00
  "fallback_utc_offset": 0,
  // the folder containing uploaded audio files. Must be supplied.
  "root_folder": "/instance/audio",
  // the folder containing log folders. optional
  "log_folder": "/instance/logs",
  // the folder where status reports should be stored. optional. defaults to `log_folder`
  "save_status_reports_folder": "/instance/status",
  // when to update the status report
  "update_status_report_at": ["00:00", "12:00"],
  // a name that can be used to identify the instance that sent the notification
  // in an email
  "name": "Testing notifier"
}
```

The first argument to `toad_notification_system.py` is the config path. Use that
to override the default config file path.

Note that `email_alert_list.txt` is a file in the same Dropbox directory containing a newline-delimited list of emails to send notifications to.
`pause_duration` is the number of seconds to wait before letting a sensor trigger another notification after it has previously triggered one.
`root_folder` is the location of the Dropbox directory where the files are stored.

## Customization

Be sure to rebuild docker image after customization.

### Cron schedule

Edit the schedule in the `crontab` file.

Every a schedule like: 

```
0/5 * * * *
```

means run every fifth minute, starting from the zeroth minute of the hour.
