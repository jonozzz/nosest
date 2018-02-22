'''
Created on Mar 13, 2017

@author: jono
'''
import json
import logging
import os

import yaml

import bottle
from f5test.base import AttrDict
from f5test.utils.cm import isofile, version_from_metadata
from f5test.utils.exbuilder.python import Literal, String, In, Or
from f5test.web.tasks import nosetests

from .common import (CONFIG, TEMPLATE_DIR, get_harness, NOSETESTS_ARGS,
                     app as common_app)


app = bottle.Bottle()
LOG = logging.getLogger(__name__)


@app.route('/bvt/deviso', method='POST')
def bvt_deviso_post():
    """ Handles requests from Dev team for user builds ISOs.

        Input POST request looks similar to this:

    { '_referer': 'http://shiraz/internaltest',
    u 'module': [u 'access', u 'adc', u 'afm', u 'asm', u 'avr', u 'cloud', u 'device', u 'system', u 'platform'],
    u 'bigip_v': u '12.0.0',
    u 'hfiso': u '/path/to/hf.iso',
    u 'iso': u '/path/to/base.iso',
    u 'custom iso': u'/path/to/custom.iso',
    u 'custom hf iso': u'/path/to/custom-hf.iso',
    u 'ui': False,
    u 'testruntype': u 'biq-standard-bvt',
    u 'ha': [u 'standalone'],
    u 'email': u 'foo@foo.com'    }
    """
    LOG.info("DEVISO: Called")
    # BVTINFO_PROJECT_PATTERN = '(\D+)?(\d+\.\d+\.\d+)-?(hf\d+)?'
    DEFAULT_SUITE = 'bvt'
    SUITES = {'bvt': '%s/' % CONFIG.paths.current,
              'dev': '%s/cloud/external/devtest_wrapper.py' % CONFIG.paths.current,
              'dev-cloud': '%s/cloud/external/restservicebus.py' % CONFIG.paths.current
              }
    CONFIG_FILE = 'config/shared/web_deviso_request.yaml'

    BIGIP_V = CONFIG.bigip_versions
    AUTOMATION_RUN_TYPES = CONFIG.automation_run_types

    # For people who don't like to set the application/json header.
    data = AttrDict(json.load(bottle.request.body))
    # data = bottle.request.json
    LOG.info("DEVISO: POST Request: " + str(data))
    data._referer = bottle.request.url

    our_config = AttrDict(yaml.load(open(get_harness('bigiq')).read()))

    # Prepare placeholders in our config
    our_config.update({'stages': {'main': {'setup': {'install': {'parameters': {}}}}}})
    our_config.update({'stages': {'main': {'setup': {'install-bigips': {'parameters': {}}}}}})
    our_config.update({'plugins': {'email': {'to': [], 'variables': {}}}})

    plugins = our_config.plugins
    # Append submitter's email to recipient list
    if data.get('email'):
        plugins.email.to.append(data['email'])
    plugins.email.to.extend(CONFIG.web.recipients)

    # Set BIGIP version config
    if data.get('bigip_v') in BIGIP_V:
        bigip_cfg = BIGIP_V[data['bigip_v']]
    else:
        bigip_cfg = BIGIP_V['default']

    # If a custom BIG-IP Base is specified, then do NOT append this .yaml
    if data.get('custom_bigip_iso') is None:
        our_config.setdefault('$extends', []).append(bigip_cfg)

    # Set BIG-IQ version and build in the install stage
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

    # Set the BIG-IP version and build in the install stage, if it was
    # specified in the POST request.
    if data.get('custom_bigip_iso'):
        params = our_config.stages.main.setup['install-bigips'].parameters
        params['custom iso'] = data['custom_bigip_iso']
        # Only append BIG-IP HF info if a Base was specified
        if data.get('custom_bigip_hf_iso'):
            params = our_config.stages.main.setup['install-bigips'].parameters
            params['custom hf iso'] = data['custom_bigip_hf_iso']

    args = []
    args[:] = NOSETESTS_ARGS

    # Set the NOSE rank string based on the automation type
    expr = Literal(AUTOMATION_RUN_TYPES[data['testruntype']])
    # Only Greenflash tests have extended attributes
    if v is None or v >= 'bigiq 4.5':
        # build hamode argument
        if data.ha:
            hamode = Literal('hamode')
            expr2 = Or()
            for x in data.ha:
                if x != 'standalone':
                    expr2 += [In(String(x.upper()), hamode)]
            if 'standalone' in data.ha:
                expr &= (~hamode | expr2)
            else:
                expr &= hamode & expr2

        if data.ui:
            uimode = Literal('uimode')
            if data.ui == 'api':
                expr &= ~uimode
            elif data.ui == 'ui':
                expr &= uimode & (uimode > Literal(0))
            else:
                raise ValueError('Unknown value {}'.format(data.ui))

        if data.module:
            module = Literal('module')
            expr2 = Or()
            for x in data.module:
                expr2 += [In(String(x.upper()), module)]
            expr &= (module & expr2)

    args.append('--tc-file={VENV}/%s' % CONFIG_FILE)

    # Default is our BVT suite.
    if v:
        suite = os.path.join(CONFIG.suites.root, CONFIG.suites[v.version])
    else:
        suite = SUITES[data.get('suite', DEFAULT_SUITE)]
    args.append('--tc=stages.enabled:1')
    # XXX: No quotes around the long argument value!
    args.append('--eval-attr={}'.format(str(expr)))
    args.append('--with-email')
    # args.append('--collect-only')
    args.append('--with-irack')
    args.append('{VENV}/%s' % suite)

    v = plugins.email.variables
    v.args = args
    v.iso = data.iso
    v.module = data.module
    LOG.info("DEVISO: Nose Args: " + str(v))
    LOG.info("DEVISO: our_config: " + str(our_config))

    result = nosetests.delay(our_config, args, data)  # @UndefinedVariable
    link = common_app.router.build('status', task_id=result.id)
    deviso_result = dict(status=result.status, id=result.id, link=link)
    LOG.info("DEVISO: Result: " + str(deviso_result))
    return deviso_result


@app.get('/bvt/deviso')
@bottle.jinja2_view('bvt_deviso', template_lookup=TEMPLATE_DIR)
def bvt_deviso_view(task_id=None):
    return AttrDict(name='Hello world')
