#!/usr/bin/env bash

export HOST_ADDR=$(ip -4 route list match 0/0 | awk '{print $3}')

/data/.local/bin/ipfs-publish $@