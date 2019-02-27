FROM python:3.7

LABEL author="Adam Uhlir <hello@adam-uhlir.me"
LABEL description="Allows continuously publishing static pages from Git repository to IPFS"

ARG IPFS_PUBLISH_CONFIG=/data/ipfs_publish/config.toml

RUN apt-get -y install git \
  && mkdir -p /data \
  && adduser --home /data --uid 1000 --disabled-password --ingroup users ipfs_publish \
  && chown ipfs_publish:users /data

COPY ./startup.sh /usr/bin/ipfs-publish

USER ipfs_publish

WORKDIR /app

RUN mkdir -p /data/ipfs_publish \
  && echo 'host = "localhost"\n\
port = 8080\n\
\n\
[repos]\n\
' > $IPFS_PUBLISH_CONFIG

COPY . /app
RUN pip install --user .

VOLUME /data/ipfs_publish
ENTRYPOINT ["./startup.sh"]
CMD ["server"]

# Http webhook server endpoint
EXPOSE 8080
