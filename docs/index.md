# Welcome to IPFS Publish!

![Git+IPFS=Love](./assets/love.png)

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

!!! warning "Web server warning"
    This tool is shipped with a basic web server that is mainly meant for a development environment 
    and is a single-threaded based, hence it is not meant for heavy load. As I am not expecting 
    that this tool would scale big it should be sufficient to use. If you would have the need you can 
    deploy it with some production-scale webserver that supports the `ASGI` protocol. The `ASGI` app
    can be found in `publish.http:app` package.

### pip

You can install ipfs-publish directly on your machine using `pip`:

```shell
$ pip install ipfs-publish
```

Then you can use the command `ipfs-publish` to manage your repos and/or start the webhook's server.

### Docker

If you plan to let some other users to use your ipfs-publish instance, then it might be good idea to run it inside
Docker, for at least some level isolation from rest of your system. **But it is bit more complicated to setup.**

There is automatically build official Docker image: `auhau/ipfs-publish`. The image exposes port 8080, under which the 
webhook server is listening for incoming connections. And volume on path `/data/ipfs_publish/` to persist the configuration. 
This image does not have IPFS daemon, therefore you have to provide connectivity to the daemon of your choice. 

!!! info "go-ipfs verion"
    ipfs-publish is tested with go-ipfs version **v0.4.23**! The IPFS HTTP Client should support the version up to v0.7.0, but I have not tested it yet.

Easiest way to deploy ipfs-publish is using `docker-compose`, together with `go-ipfs` as container. 
You can use this YAML configuration for it:

```yaml
version: '3'

services:
  ipfs:
    image: ipfs/go-ipfs:v0.4.23
    volumes:
      - /data/ipfs # or you can mount it directly to some directory on your system
  ipfs-publish:
    image: auhau/ipfs-publish
    environment:
      IPFS_PUBLISH_CONFIG: /data/ipfs_publish/config.toml
      IPFS_PUBLISH_VERBOSITY: 3
      IPFS_PUBLISH_IPFS_MULTIADDR: /dns4/ipfs/tcp/5001/http
    volumes:
      - /data/ipfs_publish
    depends_on:
      - ipfs
    ports:
      - 8080:8000
```

Also you can deploy it as a standalone image using `docker`, but it requires some more configuration based on your use-case. 
If you have running IPFS daemon on the host like this:

```shell
$ docker run -e IPFS_PUBLISH_CONFIG=/data/ipfs_publish/config.toml
 -e IPFS_PUBLISH_IPFS_MULTIADDR=/ip4/127.0.0.1/tcp/5001/http --network="host" auhau/ipfs_publish
```

!!! warning "Host network"
    `--network="host"` will bind the container's ports directly to the machine exposing it to the world, so be careful
    with that! With this configuration you can use `localhost` address which will address the host machine.
    
    **Be aware that this mode does not work on macOS!**
    
!!! tip "Non-host network approach"
    If you don't want to use the `--network="host"` mode, you can achieve similar behaviour if you set 
    `IPFS_PUBLISH_IPFS_HOST=$HOST_ADDR`. `HOST_ADDR` is a special environment variable, that
    is set inside the container and is resolved to IP address under which the host machine is reachable.
    
    !!! warning "IPFS Daemon API restriction"
        By default the Daemon API is listening only for connection from localhost. If you want to run the IPFS Daemon
        on the host and connect to it from container as described before, then you have to configure the IPFS Daemon 
        to listen to correct address. 
        
### systemd service
Depanding on your OS, you can create a systemd service for running the webhook's server. It will handle restarting
the service, and provides easy way how to manage it.


**ipfs-publish.service**
    
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

Moreover you can define reloading service which can automatically reload the configuration inside the server on change
and hence mitigate the current limitation of ipfs-publish. You can define it as:

**ipfs-publish-watcher.service**
```
[Unit]
Description=ipfs-publish restarter
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl restart ipfs-publish.service

[Install]
WantedBy=multi-user.target
```

**ipfs-publish-watcher.path**
```
[Path]
PathModified=<<PATH TO YOUR CONFIG>>

[Install]
WantedBy=multi-user.target
```

Remember that you have to enable&start both `.service` and `.path` units!

```shell
$ systemctl enable ipfs-publish-watcher.service && systemctl start ipfs-publish-watcher.service
$ systemctl enable ipfs-publish-watcher.path && systemctl start ipfs-publish-watcher.path
```

        
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
[?] Do you want to check-out specific branch?: <default-branch>
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

!!! warning "Restarting server after changes"
    If you do any modifications of the ipfs-publish state (eq. call `add` / `remove` commands) than
    the changes will be propagated only after restart of the ipfs-publish server!

### Environment variables overview

* `IPFS_PUBLISH_VERBOSITY` (int) - specifies verbosity level, same like the `-vvv` option.
* `IPFS_PUBLISH_EXCEPTIONS` (bool) - if `True` then any exceptions raised are not handled by the CLI (mostly for testing).
* `IPFS_PUBLISH_CONFIG` (str) - path to where the config file will be looked for.
* `IPFS_PUBLISH_IPFS_HOST` (str) - hostname where IPFS HTTP API will connect to.
* `IPFS_PUBLISH_IPFS_PORT` (int) - port which will be used for IPFS HTTP API connection.
* `IPFS_PUBLISH_IPFS_MULTIADDR` (str) - multiaddr to connect fo IPFS HTTP Daemon. Has precedence over IPFS Host & Port.

### Publishing flow

When repo is being published it follows these steps:

1. Freshly clone the Git repo into temporary directory, the default branch is checked out.
1. If `build_bin` is defined, it is executed inside root of the repo.
1. The `.git` folder is removed and if the `.ipfs_publish_ignore` file is present in root of the repo, the files 
specified in the file are removed.
1. The old pinned version is unpinned.
1. If `publish_dir` is specified, then this folder is added and pinned (if configured) to IPFS, otherwise the root of the repo is added.
1. If publishing to IPNS is configured, the IPNS entry is updated.
1. If CloudFlare DNS publishing is configured, then the latest CID is updated on configured DNS entry.
1. If `after_publish_bin` is defined, then it is executed inside root of the repo and the added CID is passed as argument.
1. Cleanup of the repo.

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
used for example to directly set the CID to your dns_link TXT record and not depend on IPNS. The published
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

### Specific branch to publish

You can configure specific branch in your Git repo that should be published. You can do so during adding adding the 
repo, or later on adding `branch=<name>` to the config:

```toml
[repos.github_com_auhau_auhau_github_io]
branch = "gh-pages"
```

### CloudFlare

As IPNS is currently not very performent for resolution, it is best practice to avoid it. In order to overcome this, there
is native support for changing DNSLink DNS record on CloudFlare provider (for other providers you have to write your own
script and use after-publish hook).

In order for this to work, ipfs-publish has to have access to CloudFlare. You have to provide a API token, for all 
possible ways how to do that see [python-cloudflare](https://github.com/cloudflare/python-cloudflare/#providing-cloudflare-username-and-api-key)
documentation.

!!! danger "DNS Access"
    Configure this with security in mind! If somebody would stole your API token, he can very effectively attack your website!
    
!!! tip "Scoped API tokens"
    Use API Tokens with smallest privileges (eq. edit DNS entry) and limit them only to Zone that is needed!
    
!!! success "Recommended setting"
    It is recommended to use the environment variable `CF_API_KEY` with API Token, preferably configured on the systemd
    unit as these files are not readable without `sudo` and the environment variables are not passed to any hooks 
    (`build` and `after_publish` script), which should provide hopefully satisfying level of security. 

If you want to add support for this later on, you have to specify Zone and DNS ID like so:

```toml
[repos.github_com_auhau_auhau_github_io.cloudflare]
zone_id = "fb91814936c9812312aasdfc57ac516e98"
dns_id = "c964dfc80ed523124d1casd513hu0a52"
```