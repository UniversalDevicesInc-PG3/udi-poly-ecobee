"""
Work on makeing this a generic session handler for all Polyglot's
"""

import requests,json,warnings
from requests.adapters import HTTPAdapter, Retry

class pgSession():

    def __init__(self,parent,l_name,logger,host,port=None,debug_level=-1):
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
        # Create our session
        self.session = requests.Session()
        # Allow for retries on all connections.
        retries = 30
        backoff_factor = .3
        status_force_list = (500, 502, 503, 504, 505, 506)
        adapter = HTTPAdapter(
                    max_retries=Retry(
                        total=retries,
                        read=retries,
                        connect=retries,
                        backoff_factor=backoff_factor,
                        status_forcelist=status_force_list,
                    )
                )
        for prefix in "http://", "https://":
            self.session.mount(prefix, adapter)

    def close(self):
        self.session.close()
        return

    def get(self,path,payload,auth=None):
        url = "https://{}{}/{}".format(self.host,self.port_s,path)
        if self.debug_level <= 0:
            self.logger.debug("Sending: url={0} payload={1}".format(url,payload))
        # No speical headers?
        headers = {
            "Content-Type": "application/json"
        }
        if auth is not None:
            headers['Authorization'] = auth
        if self.debug_level <= 1:
            self.logger.debug("headers={}".format(headers))
        # Some are getting unclosed socket warnings due to garbage collection?? no idea why, so just ignore them since we dont' care
        warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed.*<socket.socket.*>")
        #self.session.headers.update(headers)
        try:
            response = self.session.get(
                url,
                params=payload,
                headers=headers,
                timeout=(61,10)
            )
            if self.debug_level <= 1:
                self.logger.debug("url={}".format(response.url))
        # This is supposed to catch all request excpetions.
        except requests.exceptions.RequestException as e:
            self.logger.error("Connection error for %s: %s" % (url, e))
            return False
        return(self.response(response,'get'))

    def response(self,response,name):
        fname = 'reponse:'+name
        self.logger.debug(' Got: code=%s' % (response.status_code))
        if self.debug_level <= 2:
            self.logger.debug('      text=%s' % (response.text))
        json_data = False
        st = False
        if response.status_code == 200:
            self.logger.debug(' All good!')
            st = True
        elif response.status_code == 400:
            self.logger.error("Bad request: %s: text: %s" % (response.url,response.text) )
        elif response.status_code == 404:
            self.logger.error("Not Found: %s: text: %s" % (response.url,response.text) )
        elif response.status_code == 401:
            # Authentication error
            self.logger.error("Unauthorized: %s: text: %s" % (response.url,response.text) )
        elif response.status_code == 500:
            self.logger.error("Server Error: %s %s: text: %s" % (response.status_code,response.url,response.text) )
        elif response.status_code == 522:
            self.logger.error("Timeout Error: %s %s: text: %s" % (response.status_code,response.url,response.text) )
        else:
            self.logger.error("Unknown response %s: %s %s" % (response.status_code, response.url, response.text) )
            self.logger.error("Check system status: https://status.ecobee.com/")
        # No matter what, return the code and error
        try:
            json_data = json.loads(response.text)
        except (Exception) as err:
            # Only complain about this error if we didn't have an error above
            if st:
                self.logger.error('Failed to convert to json {0}: {1}'.format(response.text,err), exc_info=True)
            json_data = False
        return { 'code': response.status_code, 'data': json_data }

    def post(self,path,payload={},params={},dump=True,auth=None):
        url = "https://{}{}/{}".format(self.host,self.port_s,path)
        if dump:
            payload = json.dumps(payload)
        self.logger.debug("Sending: url={0} payload={1}".format(url,payload))
        headers = {
            'Content-Length': str(len(payload))
        }
        if 'json' in params and ( params['json'] or params['json'] == 'true'):
            headers['Content-Type'] = 'application/json'
        if auth is not None:
            headers['Authorization'] = auth
        if self.debug_level <= 1:
            self.logger.debug("headers={}".format(headers))
        #self.session.headers.update(headers)
        # Some are getting unclosed socket warnings due to garbage collection?? no idea why, so just ignore them since we dont' care
        warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed.*<socket.socket.*>")
        try:
            response = self.session.post(
                url,
                params=params,
                data=payload,
                headers=headers,
                timeout=(61,10)
            )
            if self.debug_level <= 1:
                self.logger.debug("url={}".format(response.url))
        # This is supposed to catch all request excpetions.
        except requests.exceptions.RequestException as e:
            self.logger.error("Connection error for %s: %s" % (url, e))
            return False
        return(self.response(response,'post'))

    def delete(self,path,auth=None):
        url = "https://{}{}/{}".format(self.host,self.port_s,path)
        self.logger.debug("Sending: url={0}".format(url))
        # No speical headers?
        headers = {
            "Content-Type": "application/json"
        }
        if auth is not None:
            headers['Authorization'] = auth
        if self.debug_level <= 1:
            self.logger.debug("headers={}".format(headers))
        # Some are getting unclosed socket warnings due to garbage collection?? no idea why, so just ignore them since we dont' care
        warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed.*<socket.socket.*>")
        #self.session.headers.update(headers)
        try:
            response = self.session.delete(
                url,
                headers=headers,
                timeout=(61,10)
            )
            if self.debug_level <= 1:
                self.logger.debug("url={}".format(response.url))
            self.logger.debug('delete got: {}'.format(response))
        # This is supposed to catch all request excpetions.
        except requests.exceptions.RequestException as e:
            self.logger.error("Connection error for %s: %s" % (url, e))
            return False
        return(self.response(response,'delete'))

