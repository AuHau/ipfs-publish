#!/usr/bin/env bash

repo_name=$1
secret=$2

data="{\"ref\": \"\"}"

sig=$(echo -n "${data}" | openssl dgst -sha1 -hmac "${secret}" | awk '{print "X-Hub-Signature: sha1="$1}')

curl -X POST -H "X-GitHub-Event: push" -H "Content-Type: application/json" -H "${sig}" --data "${data}" http://localhost:8000/publish/${repo_name}