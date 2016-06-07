import requests

from datetime import datetime
#from json.decoder import JSONDecodeError
from requests.auth import HTTPBasicAuth


class APIException(BaseException):
    def __init__(self, value, code=None):
        super(BaseException, self).__init__()
        self._value = value
        self.code = int(code)

    def __str__(self):
        return 'IPAM API Error: {0} ({1})'.format(self._value, self.code)


class API(object):
    def __init__(self, url, app, username, password):
        self._url = url + '/' + app + '/'
        auth = HTTPBasicAuth(username, password)
        response = requests.post(self._url + 'user/', auth=auth)
        try:
            json_response = response.json()
            if 'success' in json_response:
                if json_response['success']:
                    self._token = json_response['data']['token']
                    self._expires = datetime.strptime(json_response['data']['expires'], '%Y-%m-%d %H:%M:%S')
                else:
                    raise APIException(datetime['message'])
            else:
                raise APIException('Unknown error')
        except ValueError:
            raise APIException(response.content)

    def _request(self, request_type, path, params=None):
        url = self._url + path + '/'
        if params:
            url += '&'
            for key, value in params.items():
                url += '{0}={1}'.format(key, value)
        headers = {'phpipam-token': self._token}
        response = request_type(url, headers=headers)
        try:
            json_response = response.json()
            if 'success' in json_response:
                if json_response['success']:
                    return json_response['data']
                else:
                    raise APIException(json_response['message'], json_response['code'])
            else:
                raise APIException('Unknown error')
        except ValueError:
            raise APIException(response.content)

    def _get_request(self, path, **kwargs):
        return self._request(requests.get, path, params=kwargs)

    def _options_request(self, path, **kwargs):
        return self._request(requests.options, path, params=kwargs)

    def filter_sections(self, **kwargs):
        data = self._get_request('sections', **kwargs)
        if type(data) == dict:
            return list(data.values())
        else:
            return data

    def get_section(self, sid):
        return self._get_request('sections/{}'.format(sid))

    def get_subnets(self, sid, **kwargs):
        section = self.get_section(sid)
        sid = section['id']
        path = 'sections/{}/subnets/'.format(sid)
        data = self._get_request(path)
        result = []
        for subnet in data:
            append = True
            for key, value in kwargs.items():
                if key in subnet:
                    if str(value) != subnet[key]:
                        append = False
                else:
                    APIException('Invalid filter value: "{}"'.format(key))
                if not append:
                    break
            if append:
                result.append(subnet)
        return result

    def get_subnet(self, subnet, section=None, **kwargs):
        if section:
            sid = self.get_section(section)['id']
            kwargs['sectionId'] = sid
        return self._get_request('subnets/{}'.format(subnet), **kwargs)

    def get_addresses(self, subnet_id):
        subnet_data = self.get_subnet(subnet_id)
        subnet_id = subnet_data['id']
        return self._get_request('/subnets/{}/addresses/'.format(subnet_id))
