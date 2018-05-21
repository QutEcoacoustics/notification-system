# notification-system
A simple python and cron combination to send alerts when files are added to a dropbox folder


[![Build Status](https://travis-ci.org/QutEcoacoustics/notification-system.svg?branch=master)](https://travis-ci.org/QutEcoacoustics/notification-system)


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

## Config

Place a `config.json` file alongside `toad_functions.py` etc with the following format:
```
{
  "sendgrid_api_key": "<place your key here>",
  "dropbox_api_key": "<place your key here>",
  "send_from": "\"<project name>\" <email@example.com>",
  "filename_send_to": "email_alert_list.txt",
  "pause_duration": "3600",
  "root_folder": ""
}
```

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