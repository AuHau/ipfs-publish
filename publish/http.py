import asyncio
import logging
import sys

from quart import Quart, request, abort
from quart.json import dumps

from publish import config as config_module

app = Quart(__name__)
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)


@app.route('/publish/<repo_name>', methods=['POST'])
async def publish_endpoint(repo_name):
    """
    Endpoint for GitHub webhook

    :param repo_name:
    :return:
    """
    config = config_module.Config.factory()
    if repo_name not in config.repos:
        abort(400)

    repo = config.repos[repo_name]

    if repo.is_github:
        return await _handle_github(repo)

    return await _handle_generic(repo)


async def _handle_github(repo):
    header_signature = request.headers.get('X-Hub-Signature')
    if header_signature is None:
        abort(403)

    sha_name, signature = header_signature.split('=')
    if sha_name != 'sha1':
        abort(501)

    if not repo.is_data_signed_correctly(request.data, signature):
        abort(403)

    # Ping-Poing messages
    event = request.headers.get('X-GitHub-Event', 'ping')
    if event == 'ping':
        return dumps({'msg': 'pong'})

    if event != 'push':
        abort(501)

    loop = asyncio.get_event_loop()

    # noinspection PyAsyncCall
    loop.run_in_executor(None, repo.publish_repo)

    return 'OK'


async def _handle_generic(repo):
    secret = request.args.get('secret')

    if secret != repo.secret:
        abort(403)

    loop = asyncio.get_event_loop()

    # noinspection PyAsyncCall
    loop.run_in_executor(None, repo.publish_repo)

    return 'OK'
