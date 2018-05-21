FROM ubuntu:18.04

ENV  LC_ALL=C.UTF-8 LANG=C.UTF-8

RUN apt-get update \
    && apt-get -y install cron python3 python3-pip \
    && pip3 install pipenv

# Run cron job
COPY crontab /etc/cron.d/notification-system-cronjob
RUN chmod u+x /etc/cron.d/notification-system-cronjob \
    && touch /var/log/cron.log

# deprivledge root user
RUN useradd -d /home/ubuntu -ms /bin/bash -g root -G sudo -p ubuntu ubuntu
USER ubuntu
WORKDIR /home/ubuntu/notification_system

COPY --chown=ubuntu ./ ./

RUN pipenv install


CMD ["cron", "-f"]