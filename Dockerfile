FROM python:3.7

LABEL author="Adam Uhlir <hello@adam-uhlir.me"
LABEL description="Allows continuously publishing static pages from Git repository to IPFS"

ENV IPFS_PUBLISH_CONFIG /data/ipfs_publish/config.toml

RUN apt-get install git \
  && mkdir -p /data \
  && adduser --home /data --uid 1000 --disabled-password --ingroup users ipfs_publish \
  && chown ipfs_publish:users /data

USER ipfs_publish

WORKDIR /app
COPY . /app

RUN pip install --user . \
    && mkdir -p /data/ipfs_publish

RUN echo $'host = "localhost"\n\
port = 8080\n\
\n\
[ipfs]\n\
host = "localhost"\n\
port = 5001\n\
\n\
[repos]\n\
' > $IPFS_PUBLISH_CONFIG


ENTRYPOINT ["/data/.local/bin/ipfs-publish"]
CMD ["server"]

VOLUME /data/ipfs_publish

# Http webhook server endpoint
EXPOSE 8080

# IPFS daemon API endpoint
EXPOSE 5001
