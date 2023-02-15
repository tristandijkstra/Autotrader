# 
FROM python:3.9

WORKDIR /bot

COPY requirements.txt .

RUN pip install -r requirements.txt

ARG GITHUB "False"
ARG BINANCEKEY

COPY ./CryptoBotV1 ./CryptoBotV1
COPY ./extraction ./extraction
COPY ./strategies ./strategies
COPY ./keys* ./keys
COPY ./storedData* ./storedData

RUN if [ "$GITHUB" = "True" ]; then\
    mkdir ./keys && \
    mkdir ./storedData && \
    echo [ "$BINANCEKEY" ] >> ./keys/keys.txt



COPY __init__.py .
COPY logging.conf .
COPY rnBot.py .

RUN mkdir ./logs
RUN mkdir ./marketData
RUN mkdir ./logsData

# VOLUME [ "./logs", "./logsData"]

CMD ["python", "rnBot.py"]
