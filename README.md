# IPFS CD Publish - WIP

> Continuous Delivery of static websites from Git to IPFS

## About

This is a tool that aims to enable automatic publishing of static webpages from Git repositories into IPFS. 
It consists of three parts: small web server, republishing service and management CLI.

Web server exposes an endpoint which you use as your Git's webhook. When the hook is invoked, it clones
your repo, build it (if needed), add it to the IPFS node (pin it if configured) and publish the new IPFS address
under configured IPNS name.

Republishing service is in place to overcome IPNS limitation, where its entry's lifetime is limited.
Hence it will periodically refresh this entry.

Lastly CLI is in place to manage the repos.

### Features

* Ignore files - `.ipfs_publish_ignore` file specify entries that should be removed before adding the repo to IPFS
* Publish directory - you can publish only specific sub-directory inside the repo
* Build script - before adding to IPFS you can run script/binary inside the cloned repo
* After publish script - after the publishing to IPFS, this script is run with argument of the created IPFS address
* IPNS republishing

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
* go-ipfs
* UNIX-Like machine with public IP

**TBD**

## Usage

```shell
# Starts HTTP server & IPNS republishing service
$ ipfs-publish server &
Running on http://localhost:8080 (CTRL + C to quit)

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

# Show curretn repo
$ ipfs-publish show github_com_auhau_auhau_github_io
github_com_auhau_auhau_github_io
Git URL: https://github.com/auhau/auhau.github.io
Secret: EAHJ43UYT7LUEM4QFRZ4IFAXL
IPNS key: ipfs_publishg_github_com_auhau_auhau_github_io
IPNS lifetime: 24h
IPNS address: /ipns/QmRTqaW3AJJXmKyiNT7MqqZ4VjGtNNxPyTkgo3Q7pmoCeX/
Last IPFS address: None
Webhook address: http://localhost:8080/publish/github_com_auhau_auhau_github_io
```

## Contributing

Feel free to dive in, contributions are welcomed! [Open an issue](https://github.com/AuHau/ipfs-cd-publish/issues/new) or submit PRs.

For PRs and tips about development please see [contribution guideline](https://github.com/AuHau/ipfs-cd-publish/blob/master/CONTRIBUTING.md).

## License

[MIT ©  Adam Uhlir](https://github.com/AuHau/ipfs-cd-publish/blob/master/LICENSE)