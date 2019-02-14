# IPFS Publish

![Git+IPFS=Love](https://raw.githubusercontent.com/AuHau/ipfs-publish/master/docs/assets/love.png)

[![PyPI version](https://badge.fury.io/py/ipfs-publish.svg)](https://badge.fury.io/py/ipfs-publish) 
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ipfs-publish.svg)](https://pypi.org/project/ipfs-publish)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/ipfs-publish.svg)](https://pypi.org/project/ipfs-publish/) 
[![Docker Hub - Pulls](https://img.shields.io/docker/pulls/auhau/ipfs-publish.svg?style=flat)](https://hub.docker.com/r/auhau/ipfs-publish) 
[![codecov](https://codecov.io/gh/AuHau/ipfs-publish/branch/master/graph/badge.svg)](https://codecov.io/gh/AuHau/ipfs-publish) 
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/fd28ce2a500a4b1fab6f9a0a40e2fa80)](https://app.codacy.com/app/AuHau/ipfs-publish)
[![Updates](https://pyup.io/repos/github/AuHau/ipfs-publish/shield.svg)](https://pyup.io/repos/github/AuHau/ipfs-publish/)


> Continuous Delivery of static websites from Git to IPFS

## About

This is a tool that aims to enable automatic publishing of static webpages from Git repositories into IPFS. 
It consists of two parts: small web server and management CLI.

Web server exposes an endpoint which you use as your Git's webhook. When the hook is invoked, it clones
your repo, build it (if needed), add it to the IPFS node (pin it if configured) and publish the new IPFS address
under configured IPNS name.

CLI is in place to manage the repos.

### Features

* Ignore files - `.ipfs_publish_ignore` file specify entries that should be removed before adding the repo to IPFS
* Publish directory - you can publish only specific sub-directory inside the repo
* Publish specific branch - you can specify which branch should be published from the repo
* Build script - before adding to IPFS you can run script/binary inside the cloned repo
* After publish script - after the publishing to IPFS, this script is run with argument of the created IPFS address

### Git providers

Currently the webhook supports generic mode, where the repo's **secret** is passed through as URL's parameter.

There is also special mode for GitHub, where the **secret** should be configured as part of the Webhook's configuration. 

## Warning

**This tool is not meant as public service and only trusted Git repos should be used with it.
It can introduce serious security risk into your system as the runtime environment for the scripts is not 
isolated from rest of your machine!** 

## Install

### Requirements

* Python 3.7 and higher
* Git
* go-ipfs daemon
* UNIX-Like machine with public IP

### pip

You can install ipfs-publish directly on your machine using `pip`:

```shell
$ pip install ipfs-publish
```

Then you can use the command `ipfs-publish` to manage your repos and/or start the webhook's server.

### Docker

There is official Docker image build with name: `auhau/ipfs-publish`

Easiest way to run ipfs-publish is with docker-compose. Here is example for its configuration:

```yaml
version: '3'

services:
  ipfs:
    image: ipfs/go-ipfs:v0.4.18
    volumes:
      - /data/ipfs # or you can mount it directly to some directory on your system
  ipfs-publish:
    image: auhau/ipfs-publish
    environment:
      IPFS_PUBLISH_CONFIG: /data/ipfs_publish/config.toml
      IPFS_PUBLISH_VERBOSITY: 3
      IPFS_PUBLISH_IPFS_HOST: ipfs
      IPFS_PUBLISH_IPFS_PORT: 5001
    volumes:
      - /data/ipfs_publish
    depends_on:
      - ipfs
    ports:
      - 8080:8000
```

For more information see [documentation](https://ipfs-publish.adam-uhlir.me/#docker).

## Usage

```shell
# Add new repo
$ ipfs-publish add
[?] Git URL of the repo: https://github.com/auhau/auhau.github.io
[?] Name of the new repo: github_com_auhau_auhau_github_io
[?] Do you want to publish to IPNS? (Y/n):
[?] Path to build binary, if you want to do some pre-processing before publishing:
[?] Path to after-publish binary, if you want to do some actions after publishing:
[?] Directory to be published inside the repo. Path related to the root of the repo: /

Successfully added new repo!
Use this URL for you webhook: http://localhost:8080/publish/github_com_auhau_auhau_github_io
Also set this string as your hook's Secret: NIHT4785CVFT358GFE08RDAZG
Your IPNS address: /ipns/QmRTqaW3AJJXmKyiNT7MqqZ4VjGtNNxPyTkgo3Q7pmoCeX/

# List current enabled repos
$ ipfs-publish list
github_com_auhau_auhau_github_io

# Show details of repo
$ ipfs-publish show github_com_auhau_auhau_github_io
github_com_auhau_auhau_github_io
Git URL: https://github.com/auhau/auhau.github.io
Secret: EAHJ43UYT7LUEM4QFRZ4IFAXL
IPNS key: ipfs_publishg_github_com_auhau_auhau_github_io
IPNS lifetime: 24h
IPNS ttl: 15m
IPNS address: /ipns/QmRTqaW3AJJXmKyiNT7MqqZ4VjGtNNxPyTkgo3Q7pmoCeX/
Last IPFS address: None
Webhook address: http://localhost:8080/publish/github_com_auhau_auhau_github_io

# You can manually publish repo
$ ipfs-publish publish github_com_auhau_auhau_github_io

# Starts HTTP server & IPNS republishing service
$ ipfs-publish server &
Running on http://localhost:8080 (CTRL + C to quit)
```

## Contributing

Feel free to dive in, contributions are welcomed! [Open an issue](https://github.com/AuHau/ipfs-publish/issues/new) or submit PRs.

For PRs and tips about development please see [contribution guideline](https://github.com/AuHau/ipfs-publish/blob/master/CONTRIBUTING.md).

## License

[MIT ©  Adam Uhlir](https://github.com/AuHau/ipfs-publish/blob/master/LICENSE)