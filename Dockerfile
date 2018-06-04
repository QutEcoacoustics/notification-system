FROM python:3.6.5-alpine

ARG SUPERCRONIC_URL="https://github.com/aptible/supercronic/releases/download/v0.1.5/supercronic-linux-amd64"
ARG SUPERCRONIC_SHA1SUM=9aeb41e00cc7b71d30d33c57a2333f2c2581a201
ARG SUPERCRONIC=supercronic-linux-amd64
    

# install deps
RUN apk add --update --no-cache curl \
    && curl -fsSLO "$SUPERCRONIC_URL" \
    # install supercronic
    && echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c - \
    && chmod +x "$SUPERCRONIC" \
    && mv "$SUPERCRONIC" "/usr/local/bin/${SUPERCRONIC}" \
    && ln -s "/usr/local/bin/${SUPERCRONIC}" /usr/local/bin/supercronic \
    # clean up dependencies
    && apk del curl \
    &&  rm -rf /var/cache/apk/*

# deprivilege root user
RUN adduser -u 1000 -D alpine

WORKDIR /notification_system

COPY ./ /notification_system/
# The chown option for COPY is not supported yet on docker hub :-/
RUN chown alpine:alpine . ./*

USER alpine

ENV PATH="/home/alpine/.local/bin:${PATH}"

RUN pip3 install --user pipenv && pipenv install --deploy

CMD supercronic /notification_system/crontab
