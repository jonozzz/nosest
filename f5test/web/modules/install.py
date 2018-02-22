'''
Created on Mar 13, 2017

@author: jono
'''
import logging

import bottle
from f5test.base import AttrDict
from f5test.web.tasks import install

from .common import app as common_app, TEMPLATE_DIR


app = bottle.Bottle()
LOG = logging.getLogger(__name__)


@app.route('/install', method='POST')
def install_post():
    """Handles install requests.
    """
    LOG.info("INSTALL: Called")
    data = AttrDict(bottle.request.json)
    LOG.info("INSTALL: POST Request: " + str(data))
    options = AttrDict()
    options.admin_password = data.admin_password
    options.root_password = data.root_password
    options.product = data.product
    options.pversion = data.version
    options.pbuild = data.build or None
    options.phf = data.hotfix
    options.image = data.customiso
    if data.format == 'volumes':
        options.format_volumes = True
    elif data.format == 'partitions':
        options.format_partitions = True
    options.timeout = 900
    if data.config == 'essential':
        options.essential_config = True
    LOG.info("INSTALL: options: " + str(options))

    result = install.delay(address=data.address.strip(), options=options,  # @UndefinedVariable
                           user_input=data)
    link = common_app.router.build('status', task_id=result.id)
    install_result = dict(status=result.status, id=result.id, link=link)
    LOG.info("INSTALL: Result: " + str(install_result))
    return install_result


@app.get('/')
@app.get('/install')
@bottle.jinja2_view('install', template_lookup=TEMPLATE_DIR)
def install_view(task_id=None):
    return AttrDict(name='Hello world')
