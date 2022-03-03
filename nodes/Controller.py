#!/usr/bin/env python3


from asyncio import format_helpers
from udi_interface import Node,LOGGER,Custom,LOG_HANDLER

import sys
import json
import time
import http.client
import urllib.parse
from datetime import datetime
import os
import os.path
import re
import logging
from copy import deepcopy

from pgSession import pgSession
from nodes import Thermostat
from node_funcs import *

ECOBEE_API_URL = 'api.ecobee.com'

class Controller(Node):
    def __init__(self, poly, primary, address, name):
        super(Controller, self).__init__(poly, primary, address, name)
        self.name = 'Ecobee Controller'
        self.tokenData = {}
        self.msgi = {}
        self.in_discover = False
        self.discover_st = False
        self.refreshingTokens = False
        self.pinRun = False
        self._last_dtns = False
        self.hb = 0
        self.ready = False
        self.waiting_on_tokens = False
        self.use_oauth = False
        self.api_key = None
        self.api_key_param = None
        self.n_queue = []
        self.debug_level = 0
        #
        self.handler_config_st      = None
        self.handler_config_done_st = None
        self.handler_params_st      = None
        self.handler_nsdata_st      = None
        self.handler_data_st        = None
        self.Notices         = Custom(poly, 'notices')
        self.Data            = Custom(poly, 'customdata')
        self.Params          = Custom(poly, 'customparams')
        self.Notices         = Custom(poly, 'notices')
        #self.TypedParameters = Custom(poly, 'customtypedparams')
        #self.TypedData       = Custom(poly, 'customtypeddata')
        poly.subscribe(poly.START,             self.handler_start, address) 
        poly.subscribe(poly.CONFIG,            self.handler_config)
        poly.subscribe(poly.POLL,              self.handler_poll)
        poly.subscribe(poly.DISCOVER,          self.discover)
        poly.subscribe(poly.STOP,              self.handler_stop)
        poly.subscribe(poly.CUSTOMDATA,        self.handler_data)
        poly.subscribe(poly.CUSTOMPARAMS,      self.handler_params)
        poly.subscribe(poly.CUSTOMNS,          self.handler_nsdata)
        #poly.subscribe(poly.CUSTOMTYPEDPARAMS, self.handler_typed_params)
        #poly.subscribe(poly.CUSTOMTYPEDDATA,   self.handler_typed_data)
        poly.subscribe(poly.LOGLEVEL,          self.handler_log_level)
        poly.subscribe(poly.CONFIGDONE,        self.handler_config_done)
        poly.subscribe(poly.ADDNODEDONE,       self.node_queue)
        poly.ready()
        poly.addNode(self, conn_status="ST")

    '''
    node_queue() and wait_for_node_event() create a simple way to wait
    for a node to be created.  The nodeAdd() API call is asynchronous and
    will return before the node is fully created. Using this, we can wait
    until it is fully created before we try to use it.
    '''
    def node_queue(self, data):
        self.n_queue.append(data['address'])

    def wait_for_node_done(self):
        while len(self.n_queue) == 0:
            time.sleep(0.1)
        self.n_queue.pop()

    def add_node(self,node):
        anode = self.poly.addNode(node)
        LOGGER.debug(f'got {anode}')
        self.wait_for_node_done()
        if anode is None:
            LOGGER.error('Failed to add node address')
        return anode

    def handler_start(self):
        self.Notices.clear()
        #serverdata = self.poly.get_server_data(check_profile=False)
        LOGGER.info(f"Started Ecobee NodeServer {self.poly.serverdata['version']}")
        self.heartbeat()
        #
        # Wait for all handlers to finish
        #
        cnt = 10
        while ((self.handler_config_done_st is None or self.handler_params_st is None
             or self.handler_nsdata_st      is None or self.handler_data_st   is None)
             or self.handler_config_st      is None and cnt > 0):
            LOGGER.warning(f'Waiting for all to be loaded config={self.handler_config_st} config_done={self.handler_config_done_st} params={self.handler_params_st} data={self.handler_data_st} nsdata={self.handler_nsdata_st}... cnt={cnt}')
            time.sleep(1)
            cnt -= 1
        if cnt == 0:
            LOGGER.error("Timed out waiting for handlers to startup")
            self.exit()
        #
        # Force to false, and successful communication will fix it
        self.set_ecobee_st(False)
        #
        # Start the session
        #
        self.get_session() 
        #
        # Cloud uses OAuth, local users PIN
        #
        self.pg_test = False
        if self.use_oauth:
            self.grant_type = 'authorization_code'
            self.api_key    = self.serverdata['api_key']
            # TODO: Need a better way to tell if we are on pgtest!
            #       "logBucket": "pgc-test-logbucket-19y0vctj4zlk5",
            if self.poly.stage == 'test':
                self.pg_test = True
                LOGGER.warning("Looks like we are running on to pgtest")
                self.redirect_url = 'https://pgtest.isy.io/api/oauth/callback'
            else:
                LOGGER.warning("Looks like we are running on to pgc")
                self.redirect_url = 'https://polyglot.isy.io/api/oauth/callback'
        else:
            self.grant_type = 'ecobeePin'
            self.redirect_url = None
        #
        # Discover
        #
        self.ready = True
        self.discover()
        LOGGER.debug('done')

    def handler_config(self, cfg_data):
        LOGGER.info(f'cfg_data={cfg_data}')
        self.cfg_longPoll = int(cfg_data['longPoll'])
        self.handler_config_st = True

    def handler_config_done(self):
        LOGGER.info('enter')
        self.poly.addLogLevel('DEBUG_SESSION',9,'Debug + Session')
        self.poly.addLogLevel('DEBUG_SESSION_VERBOSE',8,'Debug + Session Verbose')
        self.handler_config_done_st = True
        LOGGER.info('exit')

    def handler_poll(self, polltype):
        if polltype == 'longPoll':
            self.longPoll()
        elif polltype == 'shortPoll':
            self.shortPoll()

    def shortPoll(self):
        if not self.ready:
            LOGGER.debug("{}:shortPoll: not run, not ready...".format(self.address))
            return False
        if self.in_discover:
            LOGGER.debug("{}:shortPoll: Skipping since discover is still running".format(self.address))
            return
        if self.waiting_on_tokens is False:
            LOGGER.debug("Nothing to do...")
            return
        elif self.waiting_on_tokens == "OAuth":
            LOGGER.debug("{}:shortPoll: Waiting for user to authorize...".format(self.address))
        else:
            # Must be waiting on our PIN Authorization
            LOGGER.debug("{}:shortPoll: Try to get tokens...".format(self.address))
            if self._getTokens(self.waiting_on_tokens):
                self.Notices.clear()
                LOGGER.info("shortPoll: Calling discover now that we have authorization...")
                self.discover()

    def longPoll(self):
        # Call discovery if it failed on startup
        LOGGER.debug("{}:longPoll".format(self.address))
        self.heartbeat()
        if not self.ready:
            LOGGER.debug("{}:longPoll: not run, not ready...".format(self.address))
            return False
        if self.waiting_on_tokens is not False:
            LOGGER.debug("{}:longPoll: not run, waiting for user to authorize...".format(self.address))
            return False
        if self.in_discover:
            LOGGER.debug("{}:longPoll: Skipping since discover is still running".format(self.address))
            return
        if self.discover_st is False:
            LOGGER.info("longPoll: Calling discover...")
            self.discover()
        self.updateThermostats()

    def heartbeat(self):
        LOGGER.debug('heartbeat hb={}'.format(self.hb))
        if self.hb == 0:
            self.reportCmd("DON",2)
            self.hb = 1
        else:
            self.reportCmd("DOF",2)
            self.hb = 0

    # sends a stop command for the nodeserver to Polyglot
    def exit(self):
        LOGGER.info('Asking Polyglot to stop me.')
        self.poly.send({"stop": {}})    # sends a stop command for the nodeserver to Polyglot

    def delete(self):
        LOGGER.warning("Nodeserver is being deleted...")
        # Ecobee delete tokens not working, need info from Ecobee
        #if self.ecobeeDelete():
        #    self.tokenData = {}

    def handler_log_level(self,level):
        LOGGER.info(f'enter: level={level}')
        if level['level'] < 10:
            LOGGER.info("Setting basic config to DEBUG...")
            LOG_HANDLER.set_basic_config(True,logging.DEBUG)
            # 9 & 8 incrase pgsession debug level
            if level == 9:
                self.debug_level = 1
            elif level == 8:
                self.debug_level = 2
        else:
            LOGGER.info("Setting basic config to WARNING...")
            LOG_HANDLER.set_basic_config(True,logging.WARNING)
        #logging.getLogger("elkm1_lib.elk").setLevel(slevel)
        LOGGER.info(f'exit: level={level}')

    def handler_nsdata(self, key, data):
        LOGGER.debug(f"key={key} data={data}")
        if key != "nsdata":
            LOGGER.info(f"Ignoring key={key} data={data}")
            return
        if data is None:
            LOGGER.warning(f"No NSDATA... Must be running locally key={key} data={data}")
            self.handler_nsdata_st = False
            return
        if 'nsdata' in key:
            LOGGER.info('Got nsdata update {}'.format(data))
            # Temporary, should be fixed in next version of PG3
            if data is None:
                msg = "No NSDATA Returned by Polyglot"
                LOGGER.error(msg)
                self.Notices['nsdata'] = msg
                self.handler_nsdata_st = False
                return

        self.Notices.delete('nsdata')
        try:
            #jdata = json.loads(data)
            if self.use_oauth:
                self.api_key = data['api_key_oauth']
            else:
                self.api_key = data['api_key_pin']
        except:
            LOGGER.error(f'failed to parse nsdata={data}',exc_info=True)
            self.handler_nsdata_st = False
            return
        self.handler_nsdata_st = True

    def handler_data(self,data):
        LOGGER.debug(f'enter: Loading data {data}')
        if data is None:
            LOGGER.warning("No custom data, must be firt run or never authorized")
            self.handler_data_st = False
            return
        self.Data.load(data)
        if 'tokenData' in data:
            self.tokenData = data['tokenData']
        self.handler_data_st = True

    def handler_params(self,params):
        LOGGER.debug(f'enter: Loading params {params}')
        self.Params.load(params)
        """
        Check all user params are available and valid
        """
        # Assume it's good unless it's not
        st = True
        #
        # In local install must manually supply api_key_pin to test.
        #
        if 'api_key' in self.Params.keys():
            if self.api_key_param != self.Params['api_key']:
                self.api_key_param = self.Params['api_key']
                self.api_key = self.api_key_param
                LOGGER.info(f'Got api_key from user params {self.api_key_param}')
                if self.handler_params_st is not None:
                    # User changed pin, do authorize
                    self.authorize("New user pin detected, will re-authorize...")

        self.handler_params_st = st
        LOGGER.debug(f'exit: st={st}')

    def get_session(self):
        self.session = pgSession(self,self.name,LOGGER,ECOBEE_API_URL,debug_level=self.debug_level)

    def authorized(self):
        if 'access_token' in self.tokenData:
            st = True
        else:
            st = False
        LOGGER.debug(f'exit: st={st}')
        return st

    def authorize(self,message):
        if self.api_key is None:
            msg = "api_key is not defined, must be running local version or there was an error retreiving it from PG3? Must fix or add custom param for local"
            LOGGER.error(msg)
            self.Notices['authorize'] = msg
            return
        self.Notices['authorize'] = message
        if self.use_oauth is True:
            self._getOAuth()
        else:
            self._getPin()

    def _reAuth(self, reason):
        # Need to re-auth!
        if self.tokenData is None or not 'access_toekn' in self.tokenData:
            LOGGER.error(f'No existing tokenData in Data: {self.tokenData}')
            # Save the old token for debug
            self.Data['tokenData_old'] = self.tokenData
        self.tokenData = {}
        self.authorize(f"Must Re-Authorize because {reason}")

    def _getPin(self):
        # Ask Ecobee for our Pin and present it to the user in a notice
        res = self.session_get('authorize',
                              {
                                  'response_type':  'ecobeePin',
                                  'client_id':      self.api_key,
                                  'scope':          'smartWrite'
                              })
        if res is False:
            self.refreshingTokens = False
            return False
        res_data = res['data']
        res_code = res['code']
        if 'ecobeePin' in res_data:
            msg = 'Please <a target="_blank" href="https://www.ecobee.com/consumerportal/">Signin to your Ecobee account</a>. Click on Profile > My Apps > Add Application and enter PIN: <b>{}</b> You have 10 minutes to complete this. The NodeServer will check every 60 seconds.'.format(res_data['ecobeePin'])
            LOGGER.info(f'_getPin: {msg}')
            self.Notices[f'getPin'] = msg
            # This will tell shortPoll to check for PIN
            self.waiting_on_tokens = res_data
        else:
            msg = f'ecobeePin Failed code={res_code}: {res_data}'
            self.Notices['getPin'] = msg

    def _getOAuthInit(self):
        """
        See if we have the oauth data stored already
        """
        sdata = {}
        if self.use_oauth:
            error = False
            if 'clientId' in self.poly.init['oauth']:
                sdata['api_client'] =  self.poly.init['oauth']['clientId']
            else:
                LOGGER.warning('Unable to find Client ID in the init oauth data: {}'.format(self.poly.init['oauth']))
                error = True
            if 'clientSecret' in self.poly.init['oauth']:
                sdata['api_key'] =  self.poly.init['oauth']['clientSecret']
            else:
                LOGGER.warning('Unable to find Client Secret in the init oauth data: {}'.format(self.poly.init['oauth']))
                error = True
            if error:
                return False
        return sdata
        
    def _getOAuth(self):
        # Do we have it?
        sdata = self._getOAuthInit()
        LOGGER.debug("_getOAuth: sdata={}".format(sdata))
        if sdata is not False:
            LOGGER.debug('Init={}'.format(sdata))
            self.serverdata['api_key'] = sdata['api_key']
            self.serverdata['api_client'] = sdata['api_client']
        else:
            url = 'https://{}/authorize?response_type=code&client_id={}&redirect_uri={}&state={}'.format(ECOBEE_API_URL,self.api_key,self.redirect_url,self.poly.init['worker'])
            msg = 'No existing Authorization found, Please <a target="_blank" href="{}">Authorize access to your Ecobee Account</a>'.format(url)
            self.Notices['oauth'] = msg
            LOGGER.warning(msg)
            self.waiting_on_tokens = "OAuth"

    def oauth(self, oauth):
        LOGGER.info('OAUTH Received: {}'.format(oauth))
        if 'code' in oauth:
            if self._getTokens(oauth):
                self.Notices.clear()
                self.discover()

    def _expire_delta(self):
        if not 'expires' in self.tokenData:
            return False
        ts_exp = datetime.strptime(self.tokenData['expires'], '%Y-%m-%dT%H:%M:%S')
        return ts_exp - datetime.now()

    def _checkTokens(self):
        if self.refreshingTokens:
            LOGGER.error('Waiting for token refresh to complete...')
            while self.refreshingTokens:
                time.sleep(.1)
        if 'access_token' in self.tokenData:
            exp_d = self._expire_delta()
            if exp_d is not False:
                # We allow for 10 long polls to refresh the token...
                if exp_d.total_seconds() < self.cfg_longPoll * 10:
                    LOGGER.info('Tokens {} expires {} will expire in {} seconds, so refreshing now...'.format(self.tokenData['refresh_token'],self.tokenData['expires'],exp_d.total_seconds()))
                    return self._getRefresh()
                else:
                    # Only print this ones, then once a minute at most...
                    sd = True
                    if 'ctdt' in self.msgi:
                        md = datetime.now() - self.msgi['ctdt']
                        if md.total_seconds() < 60:
                            sd = False
                    if sd:
                        LOGGER.debug('Tokens valid until: {} ({} seconds, longPoll={})'.format(self.tokenData['expires'],exp_d.seconds,self.cfg_longPoll))
                    self.msgi['ctdt'] = datetime.now()
                    self.set_auth_st(True)
                    return True
            else:
                LOGGER.error( 'No expires in tokenData:{}'.format(self.tokenData))
        else:
            self.set_auth_st(False)
            LOGGER.error('tokenData or access_token not available')
            return False

    # This is only called when refresh fails, when it works saveTokens clears
    # it, otherwise we get_ a race on who's customData is saved...
    def _endRefresh(self,refresh_data=False):
        LOGGER.debug('enter')
        if refresh_data is not False:
            if 'expires_in' in refresh_data:
                ts = time.time() + refresh_data['expires_in']
                refresh_data['expires'] = datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")
            self.token = deepcopy(refresh_data)
            self.set_auth_st(True)
            self.Notices.clear()
            # Save new token data in customData
            self.Data['tokenData'] = refresh_data
        self.refreshingTokens = False
        LOGGER.debug('exit')

    def _getRefresh(self):
        if 'refresh_token' in self.tokenData:
            self.refreshingTokens = True
            LOGGER.info('Attempting to refresh tokens...')
            res = self.session.post('token',
                params = {
                    'grant_type':    'refresh_token',
                    'client_id':     self.api_key,
                    'refresh_token': self.tokenData['refresh_token']
                })
            if res is False:
                self.set_ecobee_st(False)
                self._endRefresh()
                return False
            self.set_ecobee_st(True)
            res_data = res['data']
            res_code = res['code']
            if res_data is False:
                LOGGER.error('No data returned.')
            else:
                # https://www.ecobee.com/home/developer/api/documentation/v1/auth/auth-req-resp.shtml
                if 'error' in res_data:
                    self.set_ecobee_st(False)
                    self.Notices['grant_error'] = f"{res_data['error']}: {res_data['error_description']}"
                    #self.addNotice({'grant_info': "For access_token={} refresh_token={} expires={}".format(self.tokenData['access_token'],self.tokenData['refresh_token'],self.tokenData['expires'])})
                    LOGGER.error('Requesting Auth: {} :: {}'.format(res_data['error'], res_data['error_description']))
                    LOGGER.error('For access_token={} refresh_token={} expires={}'.format(self.tokenData['access_token'],self.tokenData['refresh_token'],self.tokenData['expires']))
                    # Set auth to false for now, so user sees the error, even if we correct it later...
                    # JimBo: This can only happen if our refresh_token is bad, so we need to force a re-auth
                    if res_data['error'] == 'invalid_grant':
                        exp_d = self._expire_delta()
                        if exp_d is False:
                            self._reAuth(f"{res_data['error']} No token expire data available")
                        else:
                            if exp_d.total_seconds() > 0:
                                msg = "But token still has {} seconds to expire, so assuming this is an Ecobee server issue and will try to refresh on next poll...".format(exp_d.total_seconds())
                                self.Notices['grant_info_2'] = msg
                                LOGGER.error(msg)
                            else:
                                msg = "Token expired {} seconds ago, so will have to re-auth...".format(exp_d.total_seconds())
                                self.Notices['grant_info_2'] = msg
                                LOGGER.error(msg)
                                # May need to remove the re-auth requirement because we get these and they don't seem to be real?
                                self._reAuth(f"{res_data['error']} and Token expired")
                    elif res_data['error'] == 'invalid_client':
                        # We will Ignore it because it may correct itself on the next poll?
                        LOGGER.error('Ignoring invalid_client error, will try again later for now, but may need to mark it invalid if we see more than once?  See: https://github.com/Einstein42/udi-ecobee-poly/issues/60')
                    #elif res_data['error'] == 'authorization_expired':
                    #    self._reAuth('{}'.format(res_data['error']))
                    else:
                        # Should all other errors require re-auth?
                        #self._reAuth('{}'.format(res_data['error']))
                        LOGGER.error('Unknown error, not sure what to do here.  Please Generate Log Package and Notify Author with a github issue: https://github.com/Einstein42/udi-ecobee-poly/issues')
                    self._endRefresh()
                    return False
                elif 'access_token' in res_data:
                    self._endRefresh(res_data)
                    return True
        else:
            self._reAuth(' refresh_token not Found in tokenData={}'.format(self.tokenData))
        self._endRefresh()
        return False

    def _getTokens(self, pinData):
        LOGGER.debug('Attempting to get tokens for {}'.format(pinData))
        res = self.session.post('token',
            params = {
                        'grant_type':  self.grant_type,
                        'client_id':   self.api_key,
                        'code':        pinData['code'],
                        'redirect_uri': self.redirect_url
                    })
        if res is False:
            self.set_ecobee_st(False)
            self.set_auth_st(False)
            return False
        res_data = res['data']
        res_code = res['code']
        if res_data is False:
            LOGGER.error('_getTokens: No data returned.')
            self.set_auth_st(False)
            return False
        if 'error' in res_data:
            LOGGER.error('_getTokens: {} :: {}'.format(res_data['error'], res_data['error_description']))
            self.set_auth_st(False)
            if res_data['error'] == 'authorization_expired' or res_data['error'] == 'invalid_grant':
                msg = 'Nodeserver exiting because {}, please restart when you are ready to authorize.'.format(res_data['error'])
                LOGGER.error('_getTokens: {}'.format(msg))
                self.waiting_on_tokens = False
                self.Notices.clear()
                self.Notices['getTokens'] = msg
                self.exit()
            return False
        if 'access_token' in res_data:
            self.waiting_on_tokens = False
            LOGGER.debug('Got tokens sucessfully.')
            self.Notices.clear()
            self.Notices['getTokens'] = 'Tokens obtained!'
            # Save pin_code
            if not self.Data.get('pin_code') != pinData['code']:
               self.Data['pin_code'] = pinData['code']
            self._endRefresh(res_data)
            return True
        self.set_auth_st(False)

    def updateThermostats(self,force=False):
        LOGGER.debug("{}:updateThermostats: start".format(self.address))
        thermostats = self.getThermostats()
        if not isinstance(thermostats, dict):
            LOGGER.error('Thermostats instance wasn\'t dictionary. Skipping...')
            return
        for thermostatId, thermostat in thermostats.items():
            LOGGER.debug("{}:updateThermostats: {}".format(self.address,thermostatId))
            if self.checkRev(thermostat):
                address = self.thermostatIdToAddress(thermostatId)
                tnode   = self.poly.getNode(address)
                if tnode is None:
                    LOGGER.error(f"Thermostat id '{thermostatId}' address '{address}' is not in our node list ({node}). thermostat: {{thermostat}}")
                else:
                    LOGGER.debug('Update detected in thermostat {}({}) doing full update.'.format(thermostat['name'], address))
                    fullData = self.getThermostatFull(thermostatId)
                    if fullData is not False:
                        tnode.update(thermostat, fullData)
                    else:
                        LOGGER.error('Failed to get updated data for thermostat: {}({})'.format(thermostat['name'], thermostatId))
            else:
                LOGGER.info("No {} '{}' update detected".format(thermostatId,thermostat['name']))
        LOGGER.debug("{}:updateThermostats: done".format(self.address))

    def checkRev(self, tstat):
        if tstat['thermostatId'] in self.revData:
            curData = self.revData[tstat['thermostatId']]
            if (tstat['thermostatRev'] != curData['thermostatRev']
                    or tstat['alertsRev'] != curData['alertsRev']
                    or tstat['runtimeRev'] != curData['runtimeRev']
                    or tstat['intervalRev'] != curData['intervalRev']):
                return True
        return False

    def query(self):
        self.reportDrivers()
        for node in self.poly.nodes():
            node.reportDrivers()

    def handler_stop(self):
        LOGGER.debug('NodeServer stoping...')
        self.set_ecobee_st(False)

    def thermostatIdToAddress(self,tid):
        return 't{}'.format(tid)

    def discover(self, *args, **kwargs):
        if not self.authorized():
            self.authorize("Tried to discover but not authorized") 
            return False
        # True means we are in dsocvery
        if self.in_discover:
            LOGGER.info('Discovering Ecobee Thermostats already running?')
            return True
        self.in_discover = True
        self.discover_st = False
        try:
            self.discover_st = self._discover()
        except Exception as e:
            LOGGER.error('failed: {}'.format(e),True)
            self.discover_st = False
        self.in_discover = False
        return self.discover_st

    def _discover(self, *args, **kwargs):
        LOGGER.info('Discovering Ecobee Thermostats')
        if not 'access_token' in self.tokenData:
            return False
        self.revData = {} # Intialize in case we fail
        thermostats = self.getThermostats()
        if thermostats is False:
            LOGGER.error("Discover Failed, No thermostats returned!  Will try again on next long poll")
            return False
        self.revData = deepcopy(thermostats)
        #
        # Build or update the profile first.
        #
        self.check_profile(thermostats)
        #
        # Now add our thermostats
        #
        for thermostatId, thermostat in thermostats.items():
            address = self.thermostatIdToAddress(thermostatId)
            tnode   = self.poly.getNode(address)
            if tnode is None:
                fullData = self.getThermostatFull(thermostatId)
                if fullData is not False:
                    tstat = fullData['thermostatList'][0]
                    useCelsius = True if tstat['settings']['useCelsius'] else False
                    self.add_node(Thermostat(self, address, address, thermostatId,
                                            'Ecobee - {}'.format(get_valid_node_name(thermostat['name'])),
                                            thermostat, fullData, useCelsius))
        return True

    def check_profile(self,thermostats):
        self.profile_info = get_profile_info(LOGGER)
        #
        # First get all the climate programs so we can build the profile if necessary
        #
        climates = dict()
        for thermostatId, thermostat in thermostats.items():
            # Only get program data if we have the node.
            fullData = self.getThermostatSelection(thermostatId,includeProgram=True)
            if fullData is not False:
                programs = fullData['thermostatList'][0]['program']
                climates[thermostatId] = list()
                for climate in programs['climates']:
                    climates[thermostatId].append({'name': climate['name'], 'ref':climate['climateRef']})
        LOGGER.debug("check_profile: climates={}".format(climates))
        #
        # Set Default profile version if not Found
        #
        LOGGER.info('check_profile: profile_info={}'.format(self.profile_info))
        LOGGER.info('check_profile:   customData={}'.format(self.Data))
        if not 'profile_info' in self.Data:
            update_profile = True
        elif self.profile_info['version'] == self.Data['profile_info']['version']:
            # Check if the climates are different
            update_profile = False
            LOGGER.info('check_profile: update_profile={} checking climates.'.format(update_profile))
            if 'climates' in self.Data:
                current = self.Data['climates']
                if not update_profile:
                    # Check if the climates have changed.
                    for id in climates:
                        if id in current:
                            if len(climates[id]) == len(current[id]):
                                for i in range(len(climates[id])):
                                    if climates[id][i] != current[id][i]:
                                        update_profile = True
                            else:
                                update_profile = True
                        else:
                            update_profile = True
            else:
                update_profile = True
        else:
            update_profile = True
        LOGGER.warning('check_profile: update_profile={}'.format(update_profile))
        if update_profile:
            self.write_profile(climates)
            self.poly.updateProfile()
            self.Data['profile_info'] = self.profile_info
            self.Data['climates'] = climates

    def write_profile(self,climates):
      pfx = '{}:write_profile:'.format(self.address)
      #
      # Start the nls with the template data.
      #
      en_us_txt = "profile/nls/en_us.txt"
      make_file_dir(en_us_txt)
      LOGGER.info("{0} Writing {1}".format(pfx,en_us_txt))
      nls_tmpl = open("template/en_us.txt", "r")
      nls      = open(en_us_txt,  "w")
      for line in nls_tmpl:
        nls.write(line)
      nls_tmpl.close()
      # Open the nodedef custom for writing
      nodedef_f = 'profile/nodedef/custom.xml'
      LOGGER.info("{0} Writing {1}".format(pfx,nodedef_f))
      nodedef_h = open(nodedef_f, "w")
      nodedef_h.write('<nodedefs>\n')
      # Open the editor custom for writing
      editor_f = 'profile/editor/custom.xml'
      LOGGER.info("{0} Writing {1}".format(pfx,editor_f))
      editor_h = open(editor_f, "w")
      editor_h.write('<editors>\n')
      for id in climates:
        # Read thermostat template to write the custom version.
        in_h  = open('template/thermostat.xml','r')
        for line in in_h:
            nodedef_h.write(re.sub(r'tstatid',r'{0}'.format(id),line))
        in_h.close()
        # Read the editor template to write the custom version
        in_h  = open('template/editors.xml','r')
        for line in in_h:
            line = re.sub(r'tstatid',r'{0}'.format(id),line)
            line = re.sub(r'tstatcnta',r'{0}'.format(len(climateList)-1),line)
            # This is minus 3 because we don't allow selecting vacation or smartAway, ...
            # But not currently using this because we don't have different list for
            # status and programs?
            line = re.sub(r'tstatcnt',r'{0}'.format(len(climateList)-5),line)
            editor_h.write(line)
        in_h.close()
        # Then the NLS lines.
        nls.write("\n")
        nls.write('ND-EcobeeC_{0}-NAME = Ecobee Thermostat {0} (C)\n'.format(id))
        nls.write('ND-EcobeeC_{0}-ICON = Thermostat\n'.format(id))
        nls.write('ND-EcobeeF_{0}-NAME = Ecobee Thermostat {0} (F)\n'.format(id))
        nls.write('ND-EcobeeF_{0}-ICON = Thermostat\n'.format(id))
        # ucfirst them all
        customList = list()
        for i in range(len(climateList)):
            customList.append(climateList[i][0].upper() + climateList[i][1:])
        # Now see if there are custom names
        for i in range(len(climateList)):
            name = climateList[i]
            # Find this name in the map and replace with our name.
            for cli in climates[id]:
                if cli['ref'] == name:
                    customList[i] = cli['name']
        LOGGER.debug("{} customList={}".format(pfx,customList))
        for i in range(len(customList)):
            nls.write("CT_{}-{} = {}\n".format(id,i,customList[i]))
      nodedef_h.write('</nodedefs>\n')
      nodedef_h.close()
      editor_h.write('</editors>\n')
      editor_h.close()
      nls.close()
      LOGGER.info("{} done".format(pfx))

    # Calls session.get and converts params to weird ecobee formatting.
    def session_get (self,path,data):
        if path == 'authorize':
            # All calls before with have auth token, don't reformat with json
            return self.session.get(path,data)
        else:
            res = self.session.get(path,{ 'json': json.dumps(data) },
                                    auth='{} {}'.format(self.tokenData['token_type'], self.tokenData['access_token'])
                                    )
            if res is False:
                return res
            if res['data'] is False:
                return False
            LOGGER.debug('res={}'.format(res))
            if not 'status' in res['data']:
                return res
            res_st_code = int(res['data']['status']['code'])
            if res_st_code == 0:
                return res
            LOGGER.error('Checking Bad Status Code {} for {}'.format(res_st_code,res))
            if res_st_code == 14:
                LOGGER.error( 'Token has expired, will refresh')
                # TODO: Should this be a loop instead ?
                if self._getRefresh() is True:
                    return self.session.get(path,{ 'json': json.dumps(data) },
                                     auth='{} {}'.format(self.tokenData['token_type'], self.tokenData['access_token']))
            elif res_st_code == 16:
                self._reAuth("session_get: Token deauthorized by user: {}".format(res))
            return False

    def getThermostats(self):
        if not self._checkTokens():
            LOGGER.debug('getThermostat failed. Couldn\'t get tokens.')
            return False
        LOGGER.debug('getThermostats: Getting Summary...')
        res = self.session_get('1/thermostatSummary',
                               {
                                    'selection': {
                                        'selectionType': 'registered',
                                        'selectionMatch': '',
                                        'includesEquipmentStatus': True
                                    },
                                })
        if res is False:
            self.set_ecobee_st(False)
            return False
        self.set_ecobee_st(True)
        thermostats = {}
        res_data = res['data']
        res_code = res['code']
        if res_data is False:
            LOGGER.error('Ecobee returned code {} but no data? ({})'.format(res_code,res_data))
            return thermostats
        if 'revisionList' in res_data:
            if res_data['revisionList'] is False:
                LOGGER.error('Ecobee returned code {} but no revisionList? ({})'.format(res_code,res_data['revisionList']))
            for thermostat in res_data['revisionList']:
                revisionArray = thermostat.split(':')
                thermostats['{}'.format(revisionArray[0])] = {
                    'name': revisionArray[1],
                    'thermostatId': revisionArray[0],
                    'connected': revisionArray[2],
                    'thermostatRev': revisionArray[3],
                    'alertsRev': revisionArray[4],
                    'runtimeRev': revisionArray[5],
                    'intervalRev': revisionArray[6]
                }
        return thermostats

    def getThermostatFull(self, id):
        return self.getThermostatSelection(id,True,True,True,True,True,True,True,True,True,True,True,True)

    def getThermostatSelection(self,id,
                               includeEvents=False,
                               includeProgram=False,
                               includeSettings=False,
                               includeRuntime=False,
                               includeExtendedRuntime=False,
                               includeLocation=False,
                               includeEquipmentStatus=False,
                               includeVersion=False,
                               includeUtility=False,
                               includeAlerts=False,
                               includeWeather=False,
                               includeSensors=False
                               ):
        if not self._checkTokens():
            LOGGER.error('getThermostat failed. Couldn\'t get tokens.')
            return False
        LOGGER.info('Getting Thermostat Data for {}'.format(id))
        res = self.session_get('1/thermostat',
                               {
                                   'selection': {
                                       'selectionType': 'thermostats',
                                       'selectionMatch': id,
                                       'includeEvents': includeEvents,
                                       'includeProgram': includeProgram,
                                       'includeSettings': includeSettings,
                                       'includeRuntime': includeRuntime,
                                       'includeExtendedRuntime': includeExtendedRuntime,
                                       'includeLocation': includeLocation,
                                       'includeEquipmentStatus': includeEquipmentStatus,
                                       'includeVersion': includeVersion,
                                       'includeUtility': includeUtility,
                                       'includeAlerts': includeAlerts,
                                       'includeWeather': includeWeather,
                                       'includeSensors': includeSensors
                                       }
                               }
                           )
        if self.debug_level >= 0:
            LOGGER.debug(f'done {id}')
        if self.debug_level >= 1:
            LOGGER.debug(f'data={res}')
        if res is False or res is None:
            return False
        return res['data']

    def ecobeePost(self, thermostatId, postData = {}):
        if not self._checkTokens():
            LOGGER.error('ecobeePost failed. Tokens not available.')
            return False
        LOGGER.info('Posting Update Data for Thermostat {}'.format(thermostatId))
        postData['selection'] = {
            'selectionType': 'thermostats',
            'selectionMatch': thermostatId
        }
        res = self.session.post('1/thermostat',params={'json': 'true'},payload=postData,
            auth='{} {}'.format(self.tokenData['token_type'], self.tokenData['access_token']),dump=True)
        if res is False:
            self.refreshingTokens = False
            self.set_ecobee_st(False)
            return False
        self.set_ecobee_st(True)
        if 'error' in res:
            LOGGER.error('ecobeePost: error="{}" {}'.format(res['error'], res['error_description']))
            return False
        res_data = res['data']
        res_code = res['code']
        if 'status' in res_data:
            if 'code' in res_data['status']:
                if res_data['status']['code'] == 0:
                    return True
                else:
                    LOGGER.error('Bad return code {}:{}'.format(res_data['status']['code'],res_data['status']['message']))
        return False

    def ecobeeDelete(self):
        if 'access_token' in self.tokenData:
            res = self.session.delete("/oauth2/acess_tokens/"+self.tokenData['access_token'])
            if res is False:
                return False
            if 'error' in res:
                LOGGER.error('ecobeePost: error="{}" {}'.format(res['error'], res['error_description']))
                return False
            res_data = res['data']
            res_code = res['code']
            if 'status' in res_data:
                if 'code' in res_data['status']:
                    if res_data['status']['code'] == 204:
                        LOGGER.info("Revoke successful")
                        return True
                    else:
                        LOGGER.error('Bad return code {}:{}'.format(res_data['status']['code'],res_data['status']['message']))
        else:
            LOGGER.warning("No access_token to revoke...")
        return False

    def cmd_poll(self,  *args, **kwargs):
        LOGGER.debug("{}:cmd_poll".format(self.address))
        self.updateThermostats(force=True)
        self.query()

    def cmd_query(self, *args, **kwargs):
        LOGGER.debug("{}:cmd_query".format(self.address))
        self.query()

    def set_ecobee_st(self,val):
      ival = 1 if val else 0
      LOGGER.debug("{}:set_ecobee_st: {}={}".format(self.address,val,ival))
      self.setDriver('GV1',ival)

    def set_auth_st(self,val):
      ival = 1 if val else 0
      LOGGER.debug("{}:set_auth_st: {}={}".format(self.address,val,ival))
      self.setDriver('GV3',ival)


    id = 'ECO_CTR'
    commands = {
        'DISCOVER': discover,
        'QUERY': cmd_query,
        'POLL': cmd_poll,
    }
    drivers = [
        {'driver': 'ST', 'value': 1, 'uom': 25},
        {'driver': 'GV1', 'value': 0, 'uom': 2},
        {'driver': 'GV3', 'value': 0, 'uom': 2}
    ]
