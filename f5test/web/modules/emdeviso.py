'''
Created on Mar 13, 2017

@author: jono
'''
import json
import logging

import yaml

import bottle
from f5test.base import AttrDict
from f5test.utils.cm import isofile, version_from_metadata
from f5test.web.tasks import nosetests

from .common import (CONFIG, TEMPLATE_DIR, get_harness, NOSETESTS_ARGS,
                     app as common_app)


app = bottle.Bottle()
LOG = logging.getLogger(__name__)


@app.route('/bvt/emdeviso', method='POST')
def bvt_emdeviso_post():
    """Handles requests from BIGIP teams.

    All the logic needed to translate the user input into what makes sense to
    us happens right here.
    """
    LOG.info("EMDEVISO: Called")
    CONFIG_FILE = 'config/shared/web_emdeviso_request.yaml'

    # For people who don't like to set the application/json header.
    data = AttrDict(json.load(bottle.request.body))
    LOG.info("EMDEVISO: POST Request: " + str(data))
    data._referer = bottle.request.url

    our_config = AttrDict(yaml.load(open(get_harness('em')).read()))

    # Prepare placeholders in our config
    our_config.update({'stages': {'main': {'setup': {'install': {'parameters': {}}}}}})
    our_config.update({'plugins': {'email': {'to': [], 'variables': {}}}})

    plugins = our_config.plugins

    # Append submitter's email to recipient list
    if data.get('email'):
        plugins.email.to.append(data['email'])
    plugins.email.to.extend(CONFIG.web.recipients)

    # Set version and build in the install stage
    v = None
    if data.get('iso'):
        params = our_config.stages.main.setup['install'].parameters
        params['custom iso'] = data['iso']
        v = version_from_metadata(data['iso'])

    if data.get('hfiso'):
        params = our_config.stages.main.setup['install'].parameters
        params['custom hf iso'] = data['hfiso']
        v = version_from_metadata(data['hfiso'])
        # Find the RTM ISO that goes with this HF image.
        if not data.get('iso'):
            params['custom iso'] = isofile(v.version, product=str(v.product))

    args = []
    args[:] = NOSETESTS_ARGS

    args.append('--tc-file={VENV}/%s' % CONFIG_FILE)
    args.append('--tc=stages.enabled:1')
    args.append('--eval-attr=rank > 0 and rank < 11')
    args.append('--with-email')
    # args.append('--with-bvtinfo')
    args.append('--with-irack')
    args.append('{VENV}/%s' % CONFIG.paths.em)
    LOG.info("EMDEVISO: Nose Args: " + str(args))
    LOG.info("EMDEVISO: our_config: " + str(our_config))

    result = nosetests.delay(our_config, args, data)  # @UndefinedVariable
    link = common_app.router.build('status', task_id=result.id)
    emdeviso_result = dict(status=result.status, id=result.id, link=link)
    LOG.info("EMDEVISO: Result: " + str(emdeviso_result))
    return emdeviso_result


@app.get('/bvt/emdeviso')
@bottle.jinja2_view('bvt_emdeviso', template_lookup=TEMPLATE_DIR)
def bvt_emdeviso_view(task_id=None):
    return AttrDict(name='Hello world')

