FROM python:3.9.21-alpine

ARG user=flaskUser

RUN apk update && apk upgrade
RUN apk add --no-cache sqlite git

RUN mkdir -p /app
WORKDIR /app

COPY ./app /app
RUN pip install --no-cache-dir -r requirements.txt

COPY ./config /config

EXPOSE 8080

CMD [ "python", "/app/main.py" ]