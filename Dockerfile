FROM python:3.7

LABEL author="Adam Uhlir <hello@adam-uhlir.me"
LABEL description="Allows continuously publishing static pages from Git repository to IPFS"

ENV IPFS_PUBLISH_CONFIG /data/config

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt
    && mkdir /data
    && apt-get install git

ENTRYPOINT ['ipfs-publish']
CMD ['server']
EXPOSE 8080