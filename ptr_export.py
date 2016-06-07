from api import API, APIException
from configparser import ConfigParser
from ipcalc import IP, Network
from jinja2 import Template
from hashlib import sha256


parser = ConfigParser()
parser.read('ipam.conf')

url = parser['api']['url']
app = parser['api']['app']
username = parser['api']['username']
password = parser['api']['password']
var_dir = parser['general']['var_dir']

api = API(url, app, username, password)

resources = {}
zones = {}

for zone in parser.sections():
    if zone[:5] == 'zone ':
        section = parser[zone]['section']
        if section not in resources:
            resources[section] = []
        zones[zone] = dict(parser[zone])
        zones[zone]['ns'] = zones[zone]['ns'].split(' ')
        zones[zone]['prefix'] = Network(zones[zone]['prefix'])
        zones[zone]['admin_mail'] = zones[zone]['admin_mail'].replace('@', '.')

for section_title in resources:
    subnets = {}
    hosts = {}
    resources[section_title] = []
    for subnet_data in api.get_subnets(section_title):
        try:
            if subnet_data['isFull'] == '1':
                ip = subnet_data['subnet'] + '/' + subnet_data['mask']
                domains = []
                if subnet_data['Domain Names'].strip():
                    for domain in subnet_data['Domain Names'].strip().split('\n'):
                        domains.append(domain)
                    if len(domains) > 0:
                        subnets[ip] = domains
            for host in api.get_addresses(subnet_data['id']):
                ip = host['ip']
                if ip not in hosts:
                    domains = [host['hostname'], ]
                    if host['Domain Names']:
                        for domain in host['Domain Names'].strip().split('\n'):
                            domains.append(domain)
                    hosts[ip] = domains
        except APIException as e:
            if e.code == 404:
                pass
            else:
                raise e
    for ip_address, domains in hosts.items():
        ip = IP(ip_address)
        ptr = ip.to_reverse()
        for domain in domains:
            if len(domain) > 0:
                resources[section_title].append((ip, ptr, domain.strip()))

    for subnet, domains in subnets.items():
        append = True
        net = Network(subnet)
        for ip_address in hosts:
            if IP(ip_address) in net:
                append = False
            if not append:
                break
        for subnet_2 in subnets:
            net_2 = Network(subnet_2)
            if net_2 in net and net_2.size() < net.size():
                append = False
            if not append:
                break
        if append:
            prefix, length = net.to_tuple()
            octets = int((length - length % 4) / 4)
            prefix = prefix.replace(':', '')[:octets]
            ptr = '*.{}.ip6.arpa'.format('.'.join(prefix[::-1]))
            for domain in domains:
                resources[section_title].append((net, ptr, domain.strip()))

for zone, params in zones.items():
    zone_network = params['prefix']
    section = params['section']
    template = Template(open(params['template_path']).read())
    hash_file = var_dir + '/' + zone + '.hash'
    sn_file = var_dir + '/' + zone + '.sn'
    params['records'] = []
    for network, record, value in resources[section]:
        if network in zone_network:
            params['records'].append(dict(resource=record, value=value))
    zone_definition = template.render(**params)
    zone_hash = sha256(zone_definition.encode('utf-8')).hexdigest()
    try:
        current_hash = open(hash_file).read()
        sn = int(open(sn_file).read())
    except IOError:
        sn = int(params['initial_sn']) - 1
        current_hash = ''
    if current_hash != zone_hash:
        sn += 1
    zone_definition = zone_definition.replace('[ --- serial number --- ]', str(sn))
    file = open(params['file_path'], 'w')
    file.write(zone_definition)
    file.close()
    open(hash_file, 'w').write(zone_hash)
    open(sn_file, 'w').write(str(sn))
