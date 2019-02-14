import logging
import os
import pathlib
import sys
import traceback
import typing

import click
import click_completion

from publish import publishing, exceptions, __version__, helpers, config as config_module, \
    ENV_NAME_PASS_EXCEPTIONS

logger = logging.getLogger('publish.cli')
click_completion.init()


def entrypoint(args: typing.Sequence[str], obj: typing.Optional[dict] = None):
    """
    CLI entry point, where exceptions are handled.
    """
    try:
        cli(args, obj=obj or {})
    except exceptions.IpfsPublishException as e:
        logger.error(str(e).strip())
        logger.debug(traceback.format_exc())
        exit(1)
    except Exception as e:
        if os.environ.get(ENV_NAME_PASS_EXCEPTIONS) == 'True':
            raise

        logger.error(str(e).strip())
        logger.debug(traceback.format_exc())
        exit(1)


# TODO: Add --config to specify path to the config file
@click.group()
@click.option('--quiet', '-q', is_flag=True, help="Don't print anything")
@click.option('--verbose', '-v', count=True, help="Prints additional info. More Vs, more info! (-vvv...)")
@click.option('--config', '-c', type=click.Path(dir_okay=False), help="Path to specific config file")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, quiet, verbose, config):
    """
    Management interface for ipfs_publish, that allows adding/listing/removing supported repos.

    Currently only public repositories are allowed. There is support for generic Git provider, that has to have at least
    support for webhooks. There is also specific implementation for GitHub provider as it can sign the webhook's request
    with secret.

    The tool ships with HTTP server, that needs to be running to accept the webhook's calls.
    """
    helpers.setup_logging(-1 if quiet else verbose)

    ctx.obj['config'] = config_module.Config.get_instance(pathlib.Path(config) if config else None)


@cli.command(short_help='Add new repo')
@click.option('--name', '-n', help='Name of the repo')
@click.option('--url', '-u', 'git_repo_url', help='URL of the Git repo')
@click.option('--branch', '-r', help='Git branch which should be checked out. Default: default branch')
@click.option('--ipns-key', '-k', help='Key name to be used for signing IPNS link')
@click.option('--ipns-lifetime', '-l', help='For how long IPNS record should be valid (a.k.a. lifetime). Default: 24h')
@click.option('--ipns-ttl', '-t', help='For how long IPNS record should be cached (a.k.a. ttl). Default: 15m')
@click.option('--pin/--no-pin', default=True, help='Whether the files added to IPFS should be pinned. Default: True')
@click.option('--republish/--no-republish', default=True, help='Whether the IPNS record should be periodically '
                                                               'republished. Default: True')
@click.option('--build-bin', '-b',
              help='Binary which should be executed before clean up of ignored files & publishing.')
@click.option('--after-publish-bin', '-a', help='Binary which should be executed after publishing.')
@click.option('--publish-dir', '-d', help='Directory that should be published. Default is root of the repo.')
@click.pass_context
def add(ctx, **kwargs):
    """
    Command that add new repo into the list of publishing repos. The values can be either specified using
    CLI's options, or using interactive bootstrap.

    If there is HTTP server running, it needs to be restarted in order the changes to be applied.
    """
    config: config_module.Config = ctx.obj['config']

    new_repo = publishing.bootstrap_repo(config, **kwargs)
    config.repos[new_repo.name] = new_repo
    config.save()

    click.secho('\nSuccessfully added new repo!', fg='green')

    webhook_url = click.style(f'{new_repo.webhook_url}', fg='yellow')
    click.echo(f'Use this URL for you webhook: {webhook_url}')

    if isinstance(new_repo, publishing.GithubRepo):
        click.echo(f'Also set this string as your hook\'s Secret: {click.style(new_repo.secret, fg="yellow")}')

    if new_repo.ipns_key is not None:
        click.echo(f'Your IPNS address: {click.style(new_repo.ipns_addr, fg="yellow")}')


@cli.command('list', short_help='List all enabled repos')
@click.pass_context
def listing(ctx):
    """
    List names of all repos
    """
    config = ctx.obj['config']

    for repo in config.repos.values():
        click.echo(repo.name)


@cli.command(short_help='Shows details for a repo')
@click.argument('name')
@click.pass_context
def show(ctx, name):
    """
    Displays details for repo with NAME, that is passed as argument.
    """
    config: config_module.Config = ctx.obj['config']
    repo: publishing.GenericRepo = config.repos.get(name)

    if repo is None:
        click.secho('Unknown repo!', fg='red')
        exit(1)

    click.secho(repo.name, fg='green')
    print_attribute('Git URL', repo.git_repo_url)
    print_attribute('Secret', repo.secret)
    print_attribute('IPNS key', repo.ipns_key)
    print_attribute('IPNS lifetime', repo.ipns_lifetime)
    print_attribute('IPNS ttl', repo.ipns_ttl)
    print_attribute('IPNS address', repo.ipns_addr)
    print_attribute('Last IPFS address', repo.last_ipfs_addr)
    print_attribute('Webhook address', f'{repo.webhook_url}')


@cli.command(short_help='Remove repo')
@click.option('--keep-pinned', is_flag=True, help='Will not remove the repo\'s content from the IPFS node')
@click.option('--keep-ipns', is_flag=True, help='Will not remove the IPNS key from the IPFS node')
@click.argument('name')
@click.pass_context
def rm(ctx, name, keep_pinned=False, keep_ipns=False):
    """
    Removes the repo from the IPFS Publish.

    It will by default cleanup the resources inside IPFS node. Eq. remove IPNS key and unpin the content. You can keep
    the resources if you use the specific options, just be aware that keeping the IPNS key, will resolve in continuation
    of republishing of the IPNS entry. And keeping pinned content will result in still serving the file.
    """
    config: config_module.Config = ctx.obj['config']
    repo: publishing.GenericRepo = config.repos.get(name)

    if repo is None:
        click.secho('Unknown repo!', fg='red')
        exit(1)

    if not keep_ipns:
        config.ipfs.key_rm(repo.ipns_key)

    if not keep_pinned and repo.last_ipfs_addr:
        config.ipfs.pin_rm(repo.last_ipfs_addr)

    del config.repos[name]
    config.save()

    click.echo('Repo successfully removed!')


@cli.command(short_help='Publish repo')
@click.argument('name')
@click.pass_context
def publish(ctx, name):
    """
    Will immediately publish repo based on its configuration.
    """
    config: config_module.Config = ctx.obj['config']
    repo: publishing.GenericRepo = config.repos.get(name)

    if repo is None:
        click.secho('Unknown repo!', fg='red')
        exit(1)

    repo.publish_repo()
    click.echo('Repo successfully published!')


@cli.command(short_help='Starts HTTP server')
@click.option('--port', '-p', type=int, help='Fort number')
@click.option('--host', '-h', help='Hostname on which the server will listen')
@click.pass_context
def server(ctx, host=None, port=None):
    """
    Command that starts webserver and republishing service.

    Webserver expose endpoint for the Webhook calls. Republishing service serves for refreshing IPNS entry, that have
    limited lifetime.

    When any configuration of the ipfs_publish is changed this command needs to be restarted.
    """
    from publish import http
    config: config_module.Config = ctx.obj['config']
    app = http.app

    host = host or config['host'] or 'localhost'
    port = port or config['port'] or 8080

    logger.info(f'Launching server on {host}:{port}')
    app.run(host, port)


def print_attribute(name, value):
    click.echo('{}: {}'.format(
        click.style(name, fg='white', dim=1),
        value
    ))


def main():
    entrypoint(sys.argv[1:])


if __name__ == '__main__':
    main()
