"""
Generic session handler for Polyglot nodeservers.

Polling/rate-limit hardening (April 2026):
  - Bounded retry policy (Fix A): retries reduced from 30 to 3, only idempotent
    GETs are auto-retried; POST/DELETE never auto-retry to avoid silently
    re-issuing non-idempotent writes against the upstream API.
  - HTTP 429 handling (Fix B): the response handler honors Retry-After and
    records a rate_limited_until timestamp so the caller can short-circuit
    further requests until the window elapses.
  - Request counters (Fix K): per-bucket counters are exposed to the caller
    for observability of polling volume.
  - Timeout tuple order (cleanup): requests expects (connect, read); changed
    from the previous (61, 10) to (10, 61).
"""

import requests, json, warnings, time
from requests.adapters import HTTPAdapter, Retry


class pgSession():

    def __init__(self, parent, l_name, logger, host, port=None, debug_level=-1):
        self.parent = parent
        self.l_name = l_name
        self.logger = logger
        self.host   = host
        self.port   = port
        self.debug_level = debug_level
        if port is None:
            self.port_s = ""
        else:
            self.port_s = ':{}'.format(port)

        self.request_counts = {}
        self.rate_limited_until = 0.0

        self.session = requests.Session()

        retries = 3
        backoff_factor = 0.5
        status_force_list = (429, 500, 502, 503, 504)
        retry_kwargs = dict(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_force_list,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        try:
            retry_obj = Retry(allowed_methods=frozenset(['GET']), **retry_kwargs)
        except TypeError:
            retry_obj = Retry(method_whitelist=frozenset(['GET']), **retry_kwargs)

        adapter = HTTPAdapter(max_retries=retry_obj)
        for prefix in "http://", "https://":
            self.session.mount(prefix, adapter)

    def close(self):
        self.session.close()
        return

    def is_rate_limited(self):
        """Return remaining seconds in the current rate-limit window, else 0."""
        remaining = self.rate_limited_until - time.time()
        return int(remaining) if remaining > 0 else 0

    def get_and_reset_counts(self):
        """Return a copy of request counters and reset them to zero."""
        counts = dict(self.request_counts)
        self.request_counts = {}
        return counts

    def _bucket(self, path):
        if not path:
            return 'other'
        if path == 'authorize':
            return 'authorize'
        if path == 'token':
            return 'token'
        if 'thermostatSummary' in path:
            return 'summary'
        if 'thermostat' in path:
            return 'thermostat'
        return 'other'

    def _inc_request_count(self, method, path):
        bucket = '{}:{}'.format(method, self._bucket(path))
        self.request_counts[bucket] = self.request_counts.get(bucket, 0) + 1

    def get(self, path, payload, auth=None):
        if self.is_rate_limited():
            self.logger.warning(
                "Skipping GET %s: rate-limited for %d more seconds" % (path, self.is_rate_limited())
            )
            return False
        url = "https://{}{}/{}".format(self.host, self.port_s, path)
        if self.debug_level <= 0:
            self.logger.debug("Sending: url={0} payload={1}".format(url, payload))
        headers = {
            "Content-Type": "application/json"
        }
        if auth is not None:
            headers['Authorization'] = auth
        if self.debug_level <= 1:
            self.logger.debug("headers={}".format(headers))
        warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed.*<socket.socket.*>")
        self._inc_request_count('GET', path)
        try:
            response = self.session.get(
                url,
                params=payload,
                headers=headers,
                timeout=(10, 61)
            )
            if self.debug_level <= 1:
                self.logger.debug("url={}".format(response.url))
        except requests.exceptions.RequestException as e:
            self.logger.error("Connection error for %s: %s" % (url, e))
            return False
        return self.response(response, 'get')

    def response(self, response, name):
        fname = 'reponse:' + name
        self.logger.debug(' Got: code=%s' % (response.status_code))
        if self.debug_level <= 2:
            self.logger.debug('      text=%s' % (response.text))
        json_data = False
        st = False
        if response.status_code == 200:
            self.logger.debug(' All good!')
            st = True
        elif response.status_code == 429:
            retry_after_hdr = response.headers.get('Retry-After', '60')
            try:
                retry_after = int(retry_after_hdr)
            except (TypeError, ValueError):
                retry_after = 60
            retry_after = max(retry_after, 30)
            self.rate_limited_until = time.time() + retry_after
            self.logger.error(
                "Rate limited (429): %s Retry-After=%ss; suspending requests until window elapses"
                % (response.url, retry_after)
            )
        elif response.status_code == 400:
            self.logger.error("Bad request: %s: text: %s" % (response.url, response.text))
        elif response.status_code == 404:
            self.logger.error("Not Found: %s: text: %s" % (response.url, response.text))
        elif response.status_code == 401:
            self.logger.error("Unauthorized: %s: text: %s" % (response.url, response.text))
        elif response.status_code == 500:
            self.logger.error("Server Error: %s %s: text: %s" % (response.status_code, response.url, response.text))
        elif response.status_code == 522:
            self.logger.error("Timeout Error: %s %s: text: %s" % (response.status_code, response.url, response.text))
        else:
            self.logger.error("Unknown response %s: %s %s" % (response.status_code, response.url, response.text))
            self.logger.error("Check system status: https://status.ecobee.com/")
        try:
            json_data = json.loads(response.text)
        except (Exception) as err:
            if st:
                self.logger.error('Failed to convert to json {0}: {1}'.format(response.text, err), exc_info=True)
            json_data = False
        return {'code': response.status_code, 'data': json_data}

    def post(self, path, payload={}, params={}, dump=True, auth=None):
        if self.is_rate_limited():
            self.logger.warning(
                "Skipping POST %s: rate-limited for %d more seconds" % (path, self.is_rate_limited())
            )
            return False
        url = "https://{}{}/{}".format(self.host, self.port_s, path)
        if dump:
            payload = json.dumps(payload)
        self.logger.debug("Sending: url={0} payload={1}".format(url, payload))
        headers = {
            'Content-Length': str(len(payload))
        }
        if 'json' in params and (params['json'] or params['json'] == 'true'):
            headers['Content-Type'] = 'application/json'
        if auth is not None:
            headers['Authorization'] = auth
        if self.debug_level <= 1:
            self.logger.debug("headers={}".format(headers))
        warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed.*<socket.socket.*>")
        self._inc_request_count('POST', path)
        try:
            response = self.session.post(
                url,
                params=params,
                data=payload,
                headers=headers,
                timeout=(10, 61)
            )
            if self.debug_level <= 1:
                self.logger.debug("url={}".format(response.url))
        except requests.exceptions.RequestException as e:
            self.logger.error("Connection error for %s: %s" % (url, e))
            return False
        return self.response(response, 'post')

    def delete(self, path, auth=None):
        if self.is_rate_limited():
            self.logger.warning(
                "Skipping DELETE %s: rate-limited for %d more seconds" % (path, self.is_rate_limited())
            )
            return False
        url = "https://{}{}/{}".format(self.host, self.port_s, path)
        self.logger.debug("Sending: url={0}".format(url))
        headers = {
            "Content-Type": "application/json"
        }
        if auth is not None:
            headers['Authorization'] = auth
        if self.debug_level <= 1:
            self.logger.debug("headers={}".format(headers))
        warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed.*<socket.socket.*>")
        self._inc_request_count('DELETE', path)
        try:
            response = self.session.delete(
                url,
                headers=headers,
                timeout=(10, 61)
            )
            if self.debug_level <= 1:
                self.logger.debug("url={}".format(response.url))
            self.logger.debug('delete got: {}'.format(response))
        except requests.exceptions.RequestException as e:
            self.logger.error("Connection error for %s: %s" % (url, e))
            return False
        return self.response(response, 'delete')
