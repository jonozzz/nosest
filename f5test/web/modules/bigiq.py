'''
Created on Mar 13, 2017

@author: jono
'''
import json
import logging
import re

import yaml

import bottle
from f5test.base import AttrDict
from f5test.web.tasks import nosetests

from ..validators import min_version_validator, sanitize_atom_path
from .common import (CONFIG, TEMPLATE_DIR, get_harness, NOSETESTS_ARGS,
                     app as common_app)


app = bottle.Bottle()
LOG = logging.getLogger(__name__)


# Backward compatible with bvtinfo-style POST requests.
@app.route('/bvt/bigiq', method='POST')
@app.route('/bigip_bigiq_request', method='POST')
def bvt_bigiq_post():
    """Handles requests from BIGIP teams for BIGIQ BVT, all modules except
        ASM.

    All the logic needed to translate the user input into what makes sense to
    us happens right here.
    """
    LOG.info("BIG-IQ CM: Called")
    BVTINFO_PROJECT_PATTERN = '(\D+)?([\d+\.]{6,})-?(eng-?\w*|hf\d+|hf-\w+)?'
    CONFIG_FILE = CONFIG.web.config['bigiq-tmos']

    # For people who don't like to set the application/json header.
    data = AttrDict(json.load(bottle.request.body))
    LOG.info("BIG-IQ CM POST Request: " + str(data))
    data._referer = bottle.request.url

    our_config = AttrDict(yaml.load(open(get_harness(CONFIG, 'bigiq-tmos')).read()))

    # Prepare placeholders in our config
    our_config.update({'group_vars': {'tmos.bigip': {'f5_install': {}}}})
    our_config.update({'plugins': {'email': {'to': [], 'variables': {}}}})

    plugins = our_config.plugins

    # Append submitter's email to recipient list
    if data.get('submitted_by'):
        plugins.email.to.append(data['submitted_by'])
    plugins.email.to.extend(CONFIG.web.recipients)

    # Set version and build in the install stage
    params = our_config.group_vars['tmos.bigip'].f5_install
    match = re.match(BVTINFO_PROJECT_PATTERN, data['project'])
    if match:
        params['version'] = match.group(2)
        if match.group(3):
            params['hf'] = match.group(3)
    else:
        params['version'] = data['project']
    params['build'] = data['build']
    params['image'] = data.get('custom_iso')
    params['hfimage'] = data.get('custom_hf_iso')
    params.product = 'bigip'

    #if not min_version_validator(params.build, params.version, params.hotfix,
    #                             params.product, min_ver=CONFIG.global_min_supported):
        # raise ValueError('Requested version not supported')
    #    bottle.response.status = 406
    #    return dict(message='Requested version not supported')

    args = []
    args[:] = NOSETESTS_ARGS

    args.append('--tc-file={VENV}/%s' % CONFIG_FILE)
    args.append('--tc=stages.enabled:1')
    args.append('--eval-attr=rank >= 1 and rank <= 10')
    args.append('--with-email')
    args.append('--with-irack')
    args.append('{VENV}/%s' % CONFIG.suites.root)

    v = plugins.email.variables
    v.args = args
    v.project = data['project']
    v.version = params.version
    v.build = params.build
    LOG.info("BIG-IQ CM Nose Args: " + str(v))
    LOG.info("BIG-IQ CM ourconfig: " + str(our_config))

    result = nosetests.delay(our_config, args, data)  # @UndefinedVariable
    link = common_app.router.build('status', task_id=result.id)
    cm_result = dict(status=result.status, id=result.id, link=link)
    LOG.info("BIG-IQ CM Result: " + str(cm_result))
    return cm_result


@app.route('/bvt/atom_bigiq_bvt', method='POST')
def bvt_bigiq_post2():
    """Handles requests from BIGIP teams for BIGIQ BVT, all parts but ASM.

    All the logic needed to translate the user input into what makes sense to
    us happens right here.
    """
    LOG.info("ATOM BIGIQBVT: Called")
    HOOK_NAME = 'big-iq-bvt'
    CONFIG_FILE = CONFIG.web.config['bigiq-tmos']

    data = AttrDict(json.load(bottle.request.body))
    data._referer = bottle.request.url
    LOG.info("ATOM BIGIQBVT: POST Request: " + str(data))

    try:
        our_config = AttrDict(yaml.load(open(get_harness('bigiq-tmos')).read()))

        # Prepare placeholders in our config
        our_config.update({'group_vars': {'tmos.bigip': {'f5_install': {}}}})
        our_config.update({'plugins': {'email': {'to': [], 'variables': {}}}})
        our_config.update({'plugins': {'atom': {'bigip': {}}, 'bvtinfo': {}}})

        plugins = our_config.plugins
        # Set ATOM data
        plugins.atom.bigip.request_id = data.content.id
        plugins.atom.bigip.name = HOOK_NAME

        # Append submitter's email to recipient list
        if data.content.requestor.email:
            plugins.email.to.append(data.content.requestor.email)
        plugins.email.to.extend(CONFIG.web.recipients)

        # Set version and build in the install stage
        params = our_config.group_vars['tmos.bigip'].f5_install

        branch = data.content.build.branch
        version = data.content.build.version
        LOG.info("ATOM BIGIQBVT: POST branch/version: " + str(branch) +
                 "/" + str(version))
        params['version'] = branch.name
        params['build'] = version.primary
        if int(version.level):
            params['hf'] = version.level
            params['hfimage'] = sanitize_atom_path(data.content.build.iso)
        else:
            params['image'] = sanitize_atom_path(data.content.build.iso)
        params.product = 'bigip'

        args = []
        args[:] = NOSETESTS_ARGS

        args.append('--tc-file={VENV}/%s' % CONFIG_FILE)
        args.append('--tc=stages.enabled:1')
        args.append("--eval-attr=rank >= 5 and rank <= 10 and module and 'ASM' not in module")
        args.append('--with-email')
        args.append('--with-atom')
        if not min_version_validator(params.build, params.version, params.hf,
                                     params.product, iso=data.content.build.iso,
                                     min_ver=CONFIG.global_min_supported):
            args.append('--with-atom-no-go=The requested product/version is not supported by this test suite.')
        args.append('--with-irack')
        # args.append('--with-qkview=never')
        args.append('{VENV}/%s' % CONFIG.paths.tc)
        # args.append('{VENV}/tests/firestone/functional/standalone/adc/api/')

        v = plugins.email.variables
        v.args = args
        v.project = data.content.build.branch.name
        v.version = data.content.build.version.version
        v.build = data.content.build.version.build
        LOG.info("ATOM BIGIQBVT: Nose Args: " + str(args))
        LOG.info("ATOM BIGIQBVT: our_config: " + str(our_config))
    except Exception:
        result = dict(status=500, id=0, link="http://shiraz/")
        LOG.exception("Exception during BIG-IQ BVT processing: " + str(result))
        return result

    # return dict(config=our_config, args=args)
    result = nosetests.delay(our_config, args, data)  # @UndefinedVariable
    link = common_app.router.build('status', task_id=result.id)
    atom_result = dict(status=result.status, id=result.id, link=link)
    LOG.info("ATOM BIGIQBVT: Result: " + str(atom_result))
    return atom_result


@app.get('/bvt/bigiq')
@app.get('/bigip_bigiq_request')
@bottle.jinja2_view('bvt_bigiq', template_lookup=TEMPLATE_DIR)
def bvt_bigiq_view(task_id=None):
    return AttrDict(name='Hello world')
