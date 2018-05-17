FROM ubuntu:16.04
RUN apt-get update && apt-get -y install cron

# Run cron job
ADD crontab /etc/cron.d/notification-system-cronjob
RUN chmod u+x /etc/cron.d/notification-system-cronjob \
    && touch /var/log/cron.log

# AT: this doesn't make sense, ovewrriten later - why is it here?
#CMD cron && tail -f /var/log/cron.log

ADD toad_functions.py /
ADD toad_notification_system.py /
ADD api_keys.json /
RUN pip install dropbox
RUN pip install sendgrid

CMD ["cron", "-f"]