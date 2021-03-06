__author__ = 'Oleg Butovich'
__copyright__ = '(c) Oleg Butovich 2013'
__licence__ = 'MIT'


import json

try:
    import requests
    urllib3 = requests.packages.urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    from requests.auth import AuthBase
    from requests.cookies import cookiejar_from_dict
except ImportError:
    import sys
    sys.stderr.write("Chosen backend requires 'requests' module\n")
    sys.exit(1)


class AuthenticationError(Exception):
    def __init__(self, msg):
        super(AuthenticationError, self).__init__(msg)
        self.msg = msg

    def __str__(self):
        return self.msg

    def __repr__(self):
        return self.__str__()


class ProxmoxHTTPAuth(AuthBase):
    def __init__(self, base_url, username, password):
        response_data = requests.post(base_url + "/access/ticket",
                                      verify=False,
                                      data={"username": username, "password": password}).json()["data"]
        if response_data is None:
            raise AuthenticationError("Couldn't authenticate user: {0} to {1}".format(username, base_url + "/access/ticket"))

        self.pve_auth_cookie = response_data["ticket"]
        self.csrf_prevention_token = response_data["CSRFPreventionToken"]

    def __call__(self, r):
        r.headers["CSRFPreventionToken"] = self.csrf_prevention_token
        return r


class JsonSerializer(object):

    content_types = [
        "application/json",
        "application/x-javascript",
        "text/javascript",
        "text/x-javascript",
        "text/x-json",
        ]

    def get_accept_types(self):
        return self.content_types

    def loads(self, response):
        try:
            return json.loads(response.content)['data']
        except ValueError:
            return response.content


class ProxmoxHttpSession(requests.Session):

    def request(self, method, url, params=None, data=None, headers=None, cookies=None, files=None, auth=None,
                timeout=None, allow_redirects=True, proxies=None, hooks=None, stream=None, verify=None, cert=None,
                serializer=None):

        #filter out streams
        files = files or {}
        data = data or {}
        for k, v in data.copy().iteritems():
            if isinstance(v, file):
                files[k] = v
                del data[k]

        headers = None
        if not files and serializer:
            headers = {"content-type": 'application/x-www-form-urlencoded'}

        return super(ProxmoxHttpSession, self).request(method, url, params, data, headers, cookies, files, auth,
                                                       timeout, allow_redirects, proxies, hooks, stream, verify, cert)


class Backend(object):
    def __init__(self, host, user, password, port=8006, verify_ssl=True, mode='json', timeout=5):
        self.base_url = "https://{0}:{1}/api2/{2}".format(host, port, mode)
        self.auth = ProxmoxHTTPAuth(self.base_url, user, password)
        self.verify_ssl = verify_ssl
        self.mode = mode
        self.timeout = timeout

    def get_session(self):
        session = ProxmoxHttpSession()
        session.verify = self.verify_ssl
        session.auth = self.auth
        session.cookies = cookiejar_from_dict({"PVEAuthCookie": self.auth.pve_auth_cookie})
        session.headers['Connection'] = 'keep-alive'
        session.headers["accept"] = self.get_serializer().get_accept_types()
        return session

    def get_base_url(self):
        return self.base_url

    def get_serializer(self):
        assert self.mode == 'json'
        return JsonSerializer()
