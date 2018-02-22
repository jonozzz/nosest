'''
Created on Mar 13, 2017

@author: jono
'''
import logging
import os

import bottle
from celery.backends.cache import get_best_memcache
from f5test.base import AttrDict

from ..tasks import MyAsyncResult


app = bottle.Bottle()
LOG = logging.getLogger(__name__)
CONFIG = AttrDict()
NOSETESTS_ARGS = ['',
                  '--verbose',
                  '--verbosity=2',  # Print test names and result at the console
                  '--all-modules',  # Collect tests from all Python modules
                  '--exe',  # Look in files that have the executable bit set
                  '--nocapture',  # Don't capture stdout
                  '--console-redirect',  # Redirect console to a log file
                  ]
TEMPLATE_DIR = [os.path.join(os.path.dirname(__file__), '..', 'views')]


def get_harness(config, pool):
    """ Determine which of the set of harness should be selected for this
        task.
    """
    mc = get_best_memcache()[0](config.memcache)
    # returns a Celery Config object, then not sure what happens, no
    # docs online for this Celery method.
    key = config.web._MC_KEY + pool
    try:
        i = mc.incr(key)
    except:
        LOG.warning("Exception in Celery Memcache, defaulting to first harness")
        i = mc.set(key, 0)
    harnesses = config.web.harnesses[pool]
    harness_path = os.path.join(config.dir, harnesses[i % len(harnesses)])
    LOG.info("Selected the test harness: " + harness_path)
    return harness_path


@app.route('/status/<task_id>', name='status')
def status_handler(task_id):
    """ Use this API to get the stats of a pending/running/terminated Shiraz
        job.

        Usage:
        http://shiraz/status/89a118cb-563b-4f7c-b548-d947f7069615
        (where 89a118cb-563b-4f7c-b548-d947f7069615 is the Shiraz task ID,
        which you can get from the celery inspect active output, second to
        last field)
    """
    task = MyAsyncResult(task_id)  # @UndefinedVariable
    result = task.load_meta()
    offset = bottle.request.query.get('s')
    if offset and result and result.logs:
        last = int(offset) - (result.tip or 0)  # it should be negative
        result.logs[:] = result.logs[last:] if last else []
    value = task.result if task.successful() else None
    bottle.response.add_header('Cache-Control', 'no-cache')
    status_result = dict(status=task.status, value=value, result=result,
                         traceback=task.traceback)
    # LOG.info("STATUS: Result: " + str(status_result))
    return status_result
