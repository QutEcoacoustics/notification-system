# notification-system
A simple python and cron combination to send alerts when files are added to a dropbox folder


[![Build Status](https://travis-ci.org/QutEcoacoustics/notification-system.svg?branch=master)](https://travis-ci.org/QutEcoacoustics/notification-system)


## Setup

- Install docker
- Build Docker image: `docker build . -t qutecoacoustics/notification-sysem:latest`



## Customization

Be sure to rebuild docker image after customization.

### Cron schedule

Edit the schedule in the `crontab` file.

Every a schedule like: 

```
0/5 * * * *
```

means run every fifth minute, starting from the zeroth minute of the hour.