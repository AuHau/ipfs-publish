import asyncio
import hmac
import logging
import sys
import typing

from quart import Quart, request, abort
from quart.json import dumps

from publish import config as config_module, publishing, exceptions

app = Quart(__name__)
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

logger = logging.getLogger('publish.http')


@app.route('/publish/<repo_name>', methods=['POST'])
async def publish_endpoint(repo_name):
    """
    Endpoint for Git provider's webhook

    :param repo_name:
    :return:
    """
    config = config_module.Config.get_instance()
    if repo_name not in config.repos:
        abort(400)

    repo = config.repos[repo_name]
    handler = handler_dispatcher(repo)

    return await handler.handle_request(request)


def handler_dispatcher(repo: typing.Union[publishing.GenericRepo, publishing.GithubRepo]) -> 'GenericHandler':
    """
    Dispatch request to proper Handler based on what kind of repo the request is directed to.
    :param repo: Name of the repo
    :return:
    """
    if type(repo) is publishing.GenericRepo:
        return GenericHandler(repo)
    elif type(repo) is publishing.GithubRepo:
        return GithubHandler(repo)
    else:
        raise exceptions.HttpException('Unknown Repo\'s class!')


class GenericHandler:
    """
    Handler that serves request for Generic repos.

    It verifies that the repo's secret is passed as GET argument of the request
    """

    def __init__(self, repo: publishing.GenericRepo):
        self.repo = repo

    async def handle_request(self, req: request) -> str:
        secret = req.args.get('secret')

        if secret != self.repo.secret:
            logger.warning(f'Request for generic repo \'{self.repo.name}\' did not have valid secret parameter!')
            abort(403)

        loop = asyncio.get_event_loop()

        # noinspection PyAsyncCall
        loop.run_in_executor(None, self.repo.publish_repo)

        return 'OK'


class GithubHandler(GenericHandler):
    """
    Handler that serves request for GitHub repos.

    It verifies that the request is correctly signed with the repo's secret.
    """

    def __init__(self, repo: publishing.GithubRepo):
        super().__init__(repo)

    def is_data_signed_correctly(self, data, signature) -> bool:
        # HMAC requires the key to be bytes, but data is string
        mac = hmac.new(self.repo.secret.encode('utf-8'), msg=data, digestmod='sha1')
        if not hmac.compare_digest(str(mac.hexdigest()), signature):
            return False

        return True

    async def handle_request(self, req: request) -> str:
        header_signature = req.headers.get('X-Hub-Signature')
        if header_signature is None:
            logger.warning(f'Request for GitHub repo \'{self.repo.name}\' did not have X-Hub-Signature header!')
            abort(403)

        sha_name, signature = header_signature.split('=')
        if sha_name != 'sha1':
            logger.warning(f'Request for GitHub repo \'{self.repo.name}\' was not signed with SHA1 function!')
            abort(501)

        if not self.is_data_signed_correctly(await req.data, signature):
            logger.warning(f'Request for GitHub repo \'{self.repo.name}\' did not have valid signature!')
            abort(403)

        # Ping-Pong messages
        event = req.headers.get('X-GitHub-Event', 'ping')
        if event == 'ping':
            return dumps({'msg': 'pong'})

        if event != 'push':
            logger.warning(f'Request for GitHub repo \'{self.repo.name}\' was not result of push event!')
            abort(501)

        loop = asyncio.get_event_loop()

        # noinspection PyAsyncCall
        loop.run_in_executor(None, self.repo.publish_repo)

        return 'OK'
