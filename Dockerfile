FROM python:3.6.5-slim-stretch


ENV SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.1.5/supercronic-linux-amd64 \
    SUPERCRONIC=supercronic-linux-amd64 \
    SUPERCRONIC_SHA1SUM=9aeb41e00cc7b71d30d33c57a2333f2c2581a201

# install deps
RUN apt-get update \
    && apt-get install -y curl dumb-init \
    && curl -fsSLO "$SUPERCRONIC_URL" \
    # install supercronic
    && echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c - \
    && chmod +x "$SUPERCRONIC" \
    && mv "$SUPERCRONIC" "/usr/local/bin/${SUPERCRONIC}" \
    && ln -s "/usr/local/bin/${SUPERCRONIC}" /usr/local/bin/supercronic \
    # clean up dependencies
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Run cron job
# COPY crontab /etc/cron.d/notification-system-cronjob
# RUN chmod u+x /etc/cron.d/notification-system-cronjob \
#     && touch /var/log/cron.log

# deprivilege root user
RUN useradd -d /home/debian -m -s /bin/bash -u 1000 -p '*' -U debian


WORKDIR /notification_system

COPY ./ /notification_system/
# The chown option for COPY is not supported yet on docker hub :-/
RUN chown debian *

USER debian

ENV PATH="/home/debian/.local/bin:${PATH}"

RUN pip3 install --user pipenv && pipenv install --deploy

CMD supercronic /notification_system/crontab