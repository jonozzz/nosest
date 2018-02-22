# !/usr/bin/env python

import time
import logging

POOL_UP = "INSTANCE_STATE_UP"
HTTPD_INITSCRIPT = "/etc/init.d/httpd"
LOG = logging.getLogger(__name__)


def apachectl(cmd):
    """ stop or start apache.  cmd is one of stop | start | restart """
    LOG.warning('TODO: implement apache controls')


def apache_running():
    LOG.warning('TODO: implement apache controls')


def up_transition(soap_proxy, pool):
    """ verifies that pool transitions to up """
    for r in range(10):
        results = soap_proxy.get_monitor_instance(pool_names=[pool])
        res = results[0][0]["instance_state"]
        print res

        if res == POOL_UP:
            return True
        else:
            time.sleep(5)

    return False


def down_transition(soap_proxy, pool):
    """ verifies that pool transitions to down """
    for r in range(10):
        results = soap_proxy.get_monitor_instance(pool_names=[pool])
        res = results[0][0]["instance_state"]
        print res

        if res == POOL_UP:
            time.sleep(5)
        else:
            return True

    return False
