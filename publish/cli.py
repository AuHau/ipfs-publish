import logging
import os
import sys
import traceback

import click
import click_completion

from publish import publishing, exceptions, __version__, helpers, config as config_module

logger = logging.getLogger('publish.cli')
click_completion.init()


def entrypoint(args, obj=None):
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
        if os.environ.get('IPFS_PUBLISH_EXCEPTIONS') == '1':
            raise

        logger.error(str(e).strip())
        logger.debug(traceback.format_exc())
        exit(1)


@click.group()
@click.option('--quiet', '-q', is_flag=True, help="Don't print anything")
@click.option('--verbose', '-v', count=True, help="Prints additional info. More Vs, more info! (-vvv...)")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, quiet, verbose):
    """

    """
    helpers.setup_logging(-1 if quiet else verbose)

    ctx.obj['config'] = config_module.Config.factory()


@cli.command(short_help='Add new repo')
@click.option('--name', '-n', help='Name of the repo')
@click.option('--url', '-u', 'git_repo_url', help='URL of the Git repo')
@click.option('--ipns-key', '-k', help='Key to be used for signing IPNS link')
@click.option('--ipns-lifetime', '-l', help='For how long IPNS record should be valid')
@click.option('--pin', '-p', is_flag=True, help='Whether the files added to IPFS should be pinned')
@click.option('--republish', '-r', is_flag=True, help='Whether the IPNS record should be periodically republished')
@click.option('--build-bin', '-b', help='Binary which should be executed before clean up of ignored files & publishing.')
@click.option('--after-publish-bin', '-a', help='Binary which should be executed after publishing.')
@click.option('--publish-dir', '-d', help='Directory that should be published. Default is root of the repo.')
@click.pass_context
def add(ctx, **kwargs):
    config: config_module.Config = ctx.obj['config']

    new_repo = publishing.Repo.bootstrap_repo(config, **kwargs)
    config.repos[new_repo.name] = new_repo
    config.save()

    click.secho('\nSuccessfully added new repo!', fg='green')

    webhook_url = click.style(f'{config["host"]}{new_repo.webhook_url}', fg='yellow')
    click.echo(f'Use this URL for you webhook: {webhook_url}')

    if new_repo.is_github:
        click.echo(f'Also set this string as your hook\'s Secret: {click.style(new_repo.secret, fg="yellow")}')

    if new_repo.ipns_key is not None:
        click.echo(f'Your IPNS address: {click.style(new_repo.ipns_addr, fg="yellow")}')


@cli.command('list', short_help='List all enabled repos')
@click.pass_context
def listing(ctx):
    config = ctx.obj['config']

    for repo in config.repos.values():
        click.echo(repo.name)


@cli.command(short_help='Shows details for a repo')
@click.argument('name')
@click.pass_context
def show(ctx, name):
    config: config_module.Config = ctx.obj['config']
    repo: publishing.Repo = config.repos[name]

    click.secho(repo.name, fg='green')
    print_attribute('Git URL', repo.git_repo_url)
    print_attribute('Secret', repo.secret)
    print_attribute('IPNS key', repo.ipns_key)
    print_attribute('IPNS lifetime', repo.ipns_key)
    print_attribute('IPNS address', repo.ipns_addr)
    print_attribute('Last IPFS address', repo.last_ipfs_addr)
    print_attribute('Webhook address', f'{config["host"]}{repo.webhook_url}')


def print_attribute(name, value):
    click.echo('{}: {}'.format(
        click.style(name, fg='white', dim=1),
        value
    ))


def main():
    entrypoint(sys.argv[1:])


if __name__ == '__main__':
    main()
