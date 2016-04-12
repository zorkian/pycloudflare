#
# CloudFlare API v4 client for Python
#

import json
import requests

DEFAULT_URL = 'https://api.cloudflare.com/client/v4'


class cfIterator(object):
    def __init__(self, client, klass, getter):
        self._client = client
        self._klass = klass
        self._buffer = []
        self._total_pages = None
        self._page = 0
        self._getter = getter

    def __iter__(self):
        return self

    def next(self):
        if self._buffer:
            ret = self._buffer[0]
            self._buffer = self._buffer[1:]
            return self._klass(self._client, ret)
        if self._total_pages is not None and self._page >= self._total_pages:
            raise StopIteration()
        self._page += 1
        results = self._getter(self._page)
        if not isinstance(results['result'], list):
            raise Exception('Invalid request for iterator, results not a list!')
        if not results['result']:
            raise StopIteration()
        self._total_pages = results['result_info']['total_pages']
        self._buffer = results['result'][1:]
        return self._klass(self._client, results['result'][0])
        

class CloudFlareClient(object):
    def __init__(self, email, key, url=DEFAULT_URL):
        self.email = email
        self.key = key
        self.url = url

    def _endpoint(self, *args):
        return self.url + '/' + '/'.join(*args)

    def _get_iter(self, klass, *args, **kwargs):
        return cfIterator(
            self, klass,
            lambda page: self._get(*args, page=page, **kwargs))

    def _handle(self, req):
        try:
            obj = req.json()
            if not obj['success']:
                raise Exception('Error: %s' % (json.dumps(obj['errors']), ))
        except ValueError:
            pass
        req.raise_for_status()
        return obj

    def _headers(self):
        return {
            'X-Auth-Email': self.email,
            'X-Auth-Key': self.key,
            'Content-Type': 'application/json',
        }

    def _get(self, *args, **kwargs):
        req = requests.get(
            self._endpoint(args),
            params=kwargs,
            headers=self._headers())
        return self._handle(req)

    def _put(self, *args, **kwargs):
        req = requests.put(
            self._endpoint(args),
            data=json.dumps(kwargs),
            headers=self._headers())
        return self._handle(req)

    def _post(self, *args, **kwargs):
        req = requests.post(
            self._endpoint(args),
            data=json.dumps(kwargs),
            headers=self._headers())
        return self._handle(req)

    def _delete(self, *args):
        req = requests.delete(
            self._endpoint(args),
            headers=self._headers())
        return self._handle(req)

    def zones(self):
        return self._get_iter(cfZone, 'zones')

    def zone(self, zone_id):
        return cfZone(self, self._get('zones', zone_id)['result'])


class cfRecord(object):
    def __init__(self, client, obj):
        self._client = client
        self._obj = obj.get('result', obj)

    def __getattribute__(self, name):
        obj = object.__getattribute__(self, '_obj')
        if name == '_obj':
            return obj
        if name in obj:
            return obj[name]
        return object.__getattribute__(self, name)

    def _resetobj(self, obj):
        setattr(self, '_obj', obj.get('result', obj))


class cfZone(cfRecord):
    def dns_records(self, **kwargs):
        return self._client._get_iter(
            cfDnsRecord, 'zones', self.id, 'dns_records', **kwargs)

    def dns_record(self, record_id):
        return cfDnsRecord(self._client,
            self._client._get('zones', self.id, 'dns_records', record_id))

    def new_dns_record(self, name, type, content, ttl=1):
        ret = self._client._post(
            'zones', self.id, 'dns_records',
            name=name, type=type, content=content, ttl=ttl)
        return cfDnsRecord(self._client, ret['result'])



class cfDnsRecord(cfRecord):
    def update(self, **kwargs):
        for key, val in kwargs.iteritems():
            if key not in self._obj:
                raise Exception('Attempt to update unknown key: %s' % (key, ))
            self._obj[key] = val
        self._client._put('zones', self.zone_id, 'dns_records', self.id, **self._obj)

    def delete(self):
        self._resetobj(self._client._delete('zones', self.zone_id, 'dns_records', self.id))

