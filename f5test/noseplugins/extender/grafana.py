'''
Created on Jul 19, 2016

@author: jono
'''

# curl -X POST "http://graphite.internal.server/events/"-d '{"what": "bad code push", "tags": "production deploy", "data":"Jeff plays too much Ingress"}'

import time
import datetime
import logging

from . import ExtendedPlugin
from ...interfaces.testcase import ContextHelper
from ...base import AttrDict
from ...defaults import KIND_TMOS_BIGIQ
from ...interfaces.config import expand_devices
from f5test.interfaces.rest.emapi.objects.system import SnmpInbound,\
    SnmpV1V2cAccessRecords
from influxdb.client import InfluxDBClient
from f5test.interfaces.rest.emapi.objects.shared import DeviceInfo


LOG = logging.getLogger(__name__)


class Grafana(ExtendedPlugin):
    """
    Log events to Grafana.
    """
    enabled = False
    score = 480  # Before email

    def configure(self, options, noseconfig):
        """ Call the super and then validate and call the relevant parser for
        the configuration file passed in """
        super(Grafana, self).configure(options, noseconfig)

        self.context = ContextHelper()
        cfgifc = self.context.get_config()
        self.duts = options.get('duts',
                                cfgifc.config.
                                get('plugins', {}).
                                get('_default_', {}))
        self.first_time = True
        o = options.influxdb
        if o:
            self.client = InfluxDBClient(o.host, o.port, o.user, o.password, o.db)

    def setup_snmp(self, devices):
        for device in devices:
            if device.kind != KIND_TMOS_BIGIQ:
                continue
            rstifc = self.context.get_icontrol_rest(device=device)

            payload = SnmpInbound(contactInformation='', machineLocation='')
            address = {'address': '0.0.0.0', 'mask': '0.0.0.0'}
            payload.clientAllowList.append(address)
            rstifc.api.put(SnmpInbound.URI, payload=payload)  # @UndefinedVariable

            payload = SnmpV1V2cAccessRecords()
            payload.update(community='public', addressType='IPv4')
            rstifc.api.post(SnmpV1V2cAccessRecords.URI, payload=payload)

    def startTest(self, test, blocking_context=None):
        #if self.first_time:
        #    self.setup_snmp(expand_devices(self.duts))
        self.first_time = False

    def graphite_start(self):
        LOG.info('Graphite url: %s', self.options.graphite_url)
        context = ContextHelper()
        session = self.context.get_config().get_session()
        with context.get_rest(url=self.options.graphite_url) as rstifc:
            payload = AttrDict()
            payload.what = 'Test run started!'
            payload.tags = "testrun start"
            payload.data = "Run logs: %s" % session.get_url()
            rstifc.api.post('/events/', payload=payload)

    def now_as_timestamp(self):
        now = datetime.datetime.now()
        return int(time.mktime(now.timetuple()) * 1e3 + now.microsecond / 1e3)

    def graphite_stop(self, result):
        context = ContextHelper()
        self.options.stop_time = self.now_as_timestamp()
        session = self.context.get_config().get_session()
        result_text = "Total: %d, Fail: %d" % \
            (result.testsRun - result.notFailCount(),
             result.failCount())
        with context.get_rest(url=self.options.graphite_url) as rstifc:
            payload = AttrDict()
            payload.what = 'Test run stopped!'
            payload.tags = "testrun stop"
            payload.data = "Run logs: %s %s" % (session.get_url(), result_text)
            rstifc.api.post('/events/', payload=payload)

    def influxdb_start(self):
        value = "run started"
        session = self.context.get_config().get_session()
        self.options.start_time = self.now_as_timestamp()
        series = []
        for dut in expand_devices(self.duts):
            with self.context.get_icontrol_rest(device=dut) as rstifc:
                info = rstifc.api.get(DeviceInfo.URI)
                point = {
                    "measurement": 'events',
                    'fields': {
                        'value': value,
                    },
                    'tags': {
                        "name": "start",
                        #"host": info.managementAddress,
                        "harness": session.get_harness_id(),
                        "host": dut.address,
                        "machine": info.machineId,
                        "run": session.session,
                        "url": session.get_url(),
                    },
                }
                series.append(point)
        self.client.write_points(series)

    def influxdb_stop(self, result):
        value = "Total: %d, Fail: %d" % \
            (result.testsRun - result.notFailCount(),
             result.failCount())
        self.options.stop_time = self.now_as_timestamp() + 5000  # 5 second padding
        session = self.context.get_config().get_session()
        series = []
        for dut in expand_devices(self.duts):
            with self.context.get_icontrol_rest(device=dut) as rstifc:
                info = rstifc.api.get(DeviceInfo.URI)
                point = {
                    "measurement": 'events',
                    'fields': {
                        'value': value,
                        'total': result.testsRun - result.notFailCount(),
                        'failed': result.failCount()
                    },
                    'tags': {
                        "name": "stop",
                        #"host": info.managementAddress,
                        "harness": session.get_harness_id(),
                        "host": dut.address,
                        "machine": info.machineId,
                        "run": session.session,
                        "url": session.get_url(),
                    },
                }
                series.append(point)
        self.client.write_points(series)

    def begin(self):
        #self.graphite_start()
        self.influxdb_start()

    def finalize(self, result):
        self.influxdb_stop(result)
