#!/usr/bin/env bash

repo_name=$1
secret=$2
ref=$3
url=${4-http://localhost:8000}

data="{\"ref\": \"refs/heads/${ref}\"}"

sig=$(echo -n "${data}" | openssl dgst -sha1 -hmac "${secret}" | awk '{print "X-Hub-Signature: sha1="$1}')

curl -X POST -H "X-GitHub-Event: push" -H "Content-Type: application/json" -H "${sig}" --data "${data}" ${url}/publish/${repo_name}