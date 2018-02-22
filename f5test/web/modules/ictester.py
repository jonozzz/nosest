'''
Created on Mar 13, 2017

@author: jono
'''
import logging

import bottle
from f5test.base import AttrDict
from f5test.defaults import ADMIN_USERNAME

from ..tasks import ictester
from .common import app as common_app, TEMPLATE_DIR


app = bottle.Bottle()
LOG = logging.getLogger(__name__)


@app.route('/tester/icontrol', method='POST')
def tester_icontrol_post():
    """Handles icontrol tester requests.
    """
    LOG.info("ICONTROL: Called")
    data = AttrDict(bottle.request.json)
    options = AttrDict()
    options.username = ADMIN_USERNAME
    options.password = data.password
    options.json = True

    result = ictester.delay(address=data.address.strip(), method=data.method,  # @UndefinedVariable
                            options=options,
                            params=data.arguments, user_input=data)

    # print arguments
    link = common_app.router.build('status', task_id=result.id)
    icontrol_result = dict(status=result.status, id=result.id, link=link)
    LOG.info("ICONTROL: Result: " + str(icontrol_result))
    return icontrol_result


@app.get('/tester/icontrol')
@bottle.jinja2_view('tester_icontrol', template_lookup=TEMPLATE_DIR)
def tester_icontrol_view(task_id=None):
    return AttrDict(name='Hello world')
