
class IpfsPublishException(Exception):
    pass


class ConfigException(IpfsPublishException):
    pass


class RepoException(IpfsPublishException):
    pass


class PublishingException(IpfsPublishException):
    pass
