
class IpfsPublishException(Exception):
    """
    General exception related to IPFS Publish
    """
    pass


class ConfigException(IpfsPublishException):
    """
    Exception related to any configuration errors.
    """
    pass


class RepoException(IpfsPublishException):
    """
    Exception related to Repo class, mostly about the valid state of the repo.
    """
    pass


class PublishingException(IpfsPublishException):
    """
    Exception related to anything which goes wrong during publishing of repo.
    """
    pass


class HttpException(IpfsPublishException):
    """
    Exception related to handling HTTP requests.
    """
    pass
