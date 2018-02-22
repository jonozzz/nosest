'''
Created on Mar 13, 2017

@author: jono
'''
import logging

import bottle
from f5test.base import AttrDict

from ..tasks import confgen
from .common import CONFIG, TEMPLATE_DIR, app as common_app


app = bottle.Bottle()
LOG = logging.getLogger(__name__)


@app.route('/config', method='POST')
def config_post():
    """Handles confgen requests.
    """
    LOG.info("CONFIG: Called")
    data = AttrDict(bottle.request.json)
    LOG.info("CONFIG: POST Request: " + str(data))
    options = AttrDict(data)
    options.provision = ','.join(data.provision)
    options.irack_address = CONFIG.irack.address
    options.irack_username = CONFIG.irack.username
    options.irack_apikey = CONFIG.irack.apikey
    # options.clean = True
    options.no_sshkey = True
    if options.clean:
        options.selfip_internal = None
        options.selfip_external = None
        options.provision = None
        options.timezone = None
    LOG.info("CONFIG: options: " + str(options))

    result = confgen.delay(address=data.address.strip(), options=options,  # @UndefinedVariable
                           user_input=data)
    link = common_app.router.build('status', task_id=result.id)
    config_result = dict(status=result.status, id=result.id, link=link)
    LOG.info("CONFIG: Result: " + str(config_result))
    return config_result


@app.get('/config')
@bottle.jinja2_view('config', template_lookup=TEMPLATE_DIR)
def config_view(task_id=None):
    return AttrDict(name='Hello world')
