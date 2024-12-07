FROM python:3.9.21-alpine

ARG user=flaskUser

RUN sudo apk update && sudo apk upgrade
RUN sudo apk add --no-cache sqlite

RUN mkdir -p /app
WORKDIR /app

COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app

EXPOSE 8080

CMD [ "python", "./app.py" ]