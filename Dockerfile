FROM ubuntu:18.04
RUN apt-get update && apt-get -y install cron python3 python3-pip

# Run cron job
ADD crontab /etc/cron.d/notification-system-cronjob
RUN chmod u+x /etc/cron.d/notification-system-cronjob \
    && touch /var/log/cron.log

# AT: this doesn't make sense, overwrriten later - why is it here?
# CMD cron && tail -f /var/log/cron.log

RUN useradd -d /home/ubuntu -ms /bin/bash -g root -G sudo -p ubuntu ubuntu
USER ubuntu
WORKDIR /home/ubuntu

ADD toad_functions.py .
ADD toad_notification_system.py .
ADD requirements.txt .
ADD api_keys.json .
RUN pip install -r requirements.txt


CMD ["cron", "-f"]