import logging
import typing

import CloudFlare
import inquirer

from publish import exceptions

logger = logging.getLogger('publish.cloudflare')


def bootstrap_cloudflare() -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:
    if not inquirer.shortcuts.confirm('Do you want to update DNSLink on Cloudflare?', default=True):
        return None, None

    cf = CloudFlare.CloudFlare()
    try:
        cf.user.tokens.verify()
    except CloudFlare.exceptions.CloudFlareAPIError:
        print('>>> You don\'t have configured CloudFlare token!')
        print('>>> Either rerun this with proper configuration or specify ID of the Zone and TXT DNS entry which should be used for DNSLink.')
        print('>>> If you need help with the CloudFlare configuration see: https://github.com/cloudflare/python-cloudflare')
        zone_id = inquirer.shortcuts.text('Zone ID')
        dns_id = inquirer.shortcuts.text('DNS entry ID')
        return zone_id, dns_id

    print('>>> Lets find the right record you will want to update.')

    try:
        available_zones = cf.zones.get()
        zone_id = inquirer.shortcuts.list_input('In which zone should be the DNSLink edited?', choices=[(x['name'], x['id']) for x in available_zones])
    except CloudFlare.exceptions.CloudFlareAPIError:
        print('>>> Your token does not have sufficient rights to list zones!')
        zone_id = inquirer.shortcuts.text('Please provide Zone ID where should DNSLink be edited')

    if inquirer.shortcuts.confirm('Does the DNSLink TXT entry already exists?'):
        dns_records = cf.zones.dns_records.get(zone_id, params={'type': 'TXT', 'per_page': 100})
        dns_id = inquirer.shortcuts.list_input('Which entry you want to use?', choices=[(f'{x["name"]}: {x["content"][:40]}', x['id']) for x in dns_records])
    else:
        print('>>> Ok, lets create it then!')
        dns_name = inquirer.shortcuts.text('Where it should be placed (eq. full domain name with subdomain, it should probably start with _dnslink)')
        dns_id = cf.zones.dns_records.post(zone_id, data={'name': dns_name, 'type': 'TXT', 'content': 'dnslink='})["id"]
        print(f'>>> Entry with ID {dns_id} created!')

    return zone_id, dns_id


# TODO: Verify that cf.user.tokens.verify() works with Email & Token
# TODO: Verify that ENV configured token does not leak to scripts
class CloudFlareMixin:

    dns_id: typing.Optional[str] = None
    """
    DNS ID of TXT record where the DNSLink should be updated.
    """

    zone_id: typing.Optional[str] = None
    """
    Zone ID of the DNS record where it will be modified.
    """

    def __init__(self, dns_id: str = None, zone_id: str = None):
        if (dns_id or zone_id) and not (dns_id and zone_id):
            raise exceptions.ConfigException('You have to set both dns_id and zone_id! Only one does not make sense.')

        self.cf = CloudFlare.CloudFlare()
        self.dns_id = dns_id
        self.zone_id = zone_id

    def update_dns(self, cid: str):
        if not self.dns_id or not self.zone_id:
            raise exceptions.ConfigException('dns_id and zone_id not set. Not possible to update DNS!')

        try:
            self.cf.user.tokens.verify()
        except CloudFlare.exceptions.CloudFlareAPIError:
            raise exceptions.PublishingException('CloudFlare access not configured!')

        logger.info('Publishing new CID to CloudFlare DNSLink')

        record = self.cf.zones.dns_records.get(self.zone_id, self.dns_id)
        record['content'] = f'dnslink={cid}'
        self.cf.zones.dns_records.put(self.zone_id, self.dns_id, data=record)

