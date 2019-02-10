# Welcome to IPFS Publish!

## About

This is a tool that aims to enable automatic publishing of static webpages from Git repositories into IPFS. 
It consists of two parts: small web server and management CLI.

Web server exposes an endpoint which you use as your Git's webhook. When the hook is invoked, it clones
your repo, build it (if needed), add it to the IPFS node (pin it if configured) and publish the new IPFS address
under configured IPNS name.

CLI is in place to manage the repos.

## Installation

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

!!! tip "Service definition"
    Depanding on your OS, you can create a systemd service for running the webhook's server. It will handle restarting
    the service, and provides easy way how to manage it:
    
    ```
    [Unit]
    Description=ipfs-publish webhook server
    After=network.target
    StartLimitIntervalSec=0
    
    [Service]
    Type=simple
    Restart=always
    RestartSec=1
    User=<<your user>>
    ExecStart=ipfs-publish server
    
    [Install]
    WantedBy=multi-user.target
    ```
    
### Docker

TBD


## Usage

Upon the first invocation of the command `ipfs-publish`, you are asked to specify some general configuration, like
how to connect to the IPFS daemon etc. This process will create the config file. 

!!! info "Default config file placement"
    The default placement of the ipfs-publish's config is on path: `~/.ipfs_publish.toml`

!!! tip "Specific config's placement"
    You can use different path where the config's is to be stored using either the environment variable `IPFS_PUBLISH_CONFIG`
    or the `ipfs-publish --config <path>` option.


For available CLI commands see the `--help` page. Basic overview of usage of the CLI:

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

# Starts HTTP server & IPNS republishing service
$ ipfs-publish server &
Running on http://localhost:8080 (CTRL + C to quit)
```

### Publishing flow

When repo is being published it follows these steps:

1. Freshly clone the Git repo into temporary directory, the default branch is checked out.
2. If `build_bin` is defined, it is executed inside root of the repo.
3. The `.git` folder is removed and if the `.ipfs_publish_ignore` file is present in root of the repo, the files 
specified in the file are removed.
4. The old pinned version is unpinned.
5. If `publish_dir` is specified, then this folder is added and pinned (if configured) to IPFS, otherwise the root of the repo is added.
6. If publishing to IPNS is configured, the IPNS entry is updated.
7. If `after_publish_bin` is defined, then it is executed inside root of the repo and the added IPFS hash is passed as argument.
8. Cleanup of the repo.

### Ignore files

ipfs-publish can remove files before publishing the repo to IPFS. It works similarly like `.gitignore` except, that it
follows the Python's [glob's syntax](https://docs.python.org/3/library/glob.html), that is similar to UNIX style glob.
Hence usage of `**` is required if you want to remove files from subdirectories.

The definition of which files should be removed has to be placed in root of the repo with filename `.ipfs_publish_ignore`.

### Building binary

ipfs-publish allows you to run binary before publishing the repo. This feature can be used to build the repo before publishing it.
The binary is invoked in root of the repository and it needs to be installed and accessible to the OS user that is running
the webhook's server. It is invoked with shell, so shell's capabilities are available.

The binary can be specified during the bootstrapping of the repo using CLI , or later on added into the config file under "execute" subsection
of the repo's configuration: `[repos.<name of repo>.execute]` under name `build_bin`. Example:

```toml
[repos.github_com_auhau_auhau_github_io.execute]
build_bin = "jekyll build"
```

### After-publish binary

Similarly to building binary, there is also support for running a command after publishing to the IPFS. This can be
used for example to directly set the IPFS hash to your dns_link TXT record and not depend on IPNS. The published
IPFS address is passed as a argument to the binary.

The binary can be specified during the bootstrapping of the repo using CLI , or later on added into the config file under "execute" subsection
of the repo's configuration: `[repos.<name of repo>.execute]` under name `after_publish_bin`. Example:

```toml
[repos.github_com_auhau_auhau_github_io.execute]
after_publish_bin = "update-dns.sh"
```

### Publishing sub-directory

ipfs-publish enables you to publish only part of the repo, by specifying the `publish_dir` parameter. This can be used
together with the building binary to publish only the build site sub-folder.
