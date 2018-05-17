FROM ubuntu:16.04
RUN apt-get update && apt-get -y install cron

# Run cron job
ADD crontab /etc/cron.d/toad-cron
RUN chmod 0644 /etc/cron.d/toad-cron
RUN touch /var/log/cron.log
CMD cron && tail -f /var/log/cron.log

ADD toad_functions.py /
ADD toad_notification_system.py /
ADD api_keys.json /
RUN pip install dropbox
RUN pip install sendgrid

CMD ["cron", "-f"]