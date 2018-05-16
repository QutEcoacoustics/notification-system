FROM python:3
ADD toad_functions.py /
ADD toad_notification_system.py /
ADD api_keys.json /
RUN pip install dropbox
RUN pip install sendgrid

CMD [ "python", "./toad_notification_system.py" ]