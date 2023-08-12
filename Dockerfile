FROM python:3.8.16-slim-buster

RUN apt update
RUN apt install -y git

RUN mkdir /movebot
WORKDIR /movebot
RUN HOME=/movebot

COPY requirements.txt /movebot
COPY move_bot.py /movebot

RUN pip install -U -r requirements.txt
ENTRYPOINT ["python3"]
