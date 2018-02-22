'''
Created on Mar 13, 2017

@author: jono
'''
import json
import logging
import os
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
@app.route('/bvt/basic', method='POST')
@app.route('/bigip_bvt_request', method='POST')
def bvt_basic_post():
    """Handles requests from BIGIP teams.

    All the logic needed to translate the user input into what makes sense to
    us happens right here.
    """
    LOG.info("BASIC: Called")
    BVTINFO_PROJECT_PATTERN = '(\D+)?(\d+\.\d+\.\d+)-?(eng-?\w*|hf\d+|hf-\w+)?'
    TESTS_DEBUG = 'tests/solar/bvt/integration/filesystem/'
    CONFIG_FILE = 'config/shared/web_bvt_request.yaml'

    # For people who don't like to set the application/json header.
    data = AttrDict(json.load(bottle.request.body))
    LOG.info("BASIC: POST Request: " + str(data))
    data._referer = bottle.request.url
    # data = bottle.request.json

    # BUG: The iRack reservation-based picker is flawed. It'll always select
    # the nearest available harness, stacking all workers on just one.
#    with IrackInterface(address=CONFIG.irack.address,
#                        timeout=30,
#                        username=CONFIG.irack.username,
#                        password=CONFIG.irack.apikey,
#                        ssl=False) as irack:
#        config_dir = os.path.dirname(CONFIG_WEB_FILE)
#        harness_files = [os.path.join(config_dir, x) for x in CONFIG.web.harnesses]
#        our_config = RCMD.irack.pick_best_harness(harness_files, ifc=irack)
    our_config = AttrDict(yaml.load(open(get_harness('em')).read()))

    # Prepare placeholders in our config
    our_config.update({'stages': {'main': {'setup': {'install-bigips': {'parameters': {}}}}}})
    our_config.update({'plugins': {'email': {'to': [], 'variables': {}}}})
    our_config.update({'plugins': {'bvtinfo': {}}})

    plugins = our_config.plugins
    # Set BVTInfo data
    plugins.bvtinfo.project = data['project']
    plugins.bvtinfo.build = data['build']

    # Append submitter's email to recipient list
    if data.get('submitted_by'):
        plugins.email.to.append(data['submitted_by'])
    plugins.email.to.extend(CONFIG.web.recipients)

    # Set version and build in the install stage
    params = our_config.stages.main.setup['install-bigips'].parameters
    match = re.match(BVTINFO_PROJECT_PATTERN, data['project'])
    if match:
        params['version'] = match.group(2)
        if match.group(3):
            params['hotfix'] = match.group(3)
    else:
        params['version'] = data['project']
    params['build'] = data['build']
    params['custom iso'] = data.get('custom_iso')
    params['custom hf iso'] = data.get('custom_hf_iso')
    params.product = 'bigip'

    if not min_version_validator(params.build, params.version, params.hotfix,
                                 params.product, min_ver=CONFIG.global_min_supported):
        # raise ValueError('Requested version not supported')
        bottle.response.status = 406
        return dict(message='Requested version not supported')

    args = []
    args[:] = NOSETESTS_ARGS

    args.append('--tc-file={VENV}/%s' % CONFIG_FILE)
    if data.get('debug'):
        args.append('--tc=stages.enabled:1')
        tests = [os.path.join('{VENV}', x)
                 for x in re.split('\s+', (data.get('tests') or TESTS_DEBUG).strip())]
        args.extend(tests)
    else:
        args.append('--tc=stages.enabled:1')
        args.append('--eval-attr=rank > 0 and rank < 11')
        args.append('--with-email')
        # args.append('--with-bvtinfo')
        args.append('--with-irack')
        args.append('{VENV}/%s' % CONFIG.paths.em)

    v = plugins.email.variables
    v.args = args
    v.project = data['project']
    v.version = params.version
    v.build = params.build

    LOG.info("BASIC: our_config: " + str(our_config))
    LOG.info("BASIC: args: " + str(args))
    result = nosetests.delay(our_config, args, data)  # @UndefinedVariable
    link = common_app.router.build('status', task_id=result.id)
    basic_result = dict(status=result.status, id=result.id, link=link)
    LOG.info("BASIC: Result: " + str(basic_result))
    return basic_result


@app.route('/atom_em_bvt', method='POST')
def bvt_basic_post2():
    """Handles EM BVT requests.
    """
    LOG.info("ATOM EMBVT: Called")
    HOOK_NAME = 'em-bvt'
    TESTS_DEBUG = 'tests/solar/bvt/integration/filesystem/'
    CONFIG_FILE = 'config/shared/web_bvt_request.yaml'

    data = AttrDict(json.load(bottle.request.body))
    data._referer = bottle.request.url
    LOG.info("ATOM EMBVT: POST Request: " + str(data))

    our_config = AttrDict(yaml.load(open(get_harness('em')).read()))

    # Prepare placeholders in our config
    our_config.update({'stages': {'main': {'setup': {'install-bigips': {'parameters': {}}}}}})
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
    params = our_config.stages.main.setup['install-bigips'].parameters

    branch = data.content.build.branch
    version = data.content.build.version
    params['version'] = branch.name
    params['build'] = version.primary
    if int(version.level):
        params['hotfix'] = version.level
        params['custom hf iso'] = sanitize_atom_path(data.content.build.iso)
    else:
        params['custom iso'] = sanitize_atom_path(data.content.build.iso)
    params.product = 'bigip'

    # TODO: Remove this when bvtinfo goes offline
    # Set BVTInfo data
    plugins.bvtinfo.project = branch.name
    plugins.bvtinfo.build = version.old_build_number

    args = []
    args[:] = NOSETESTS_ARGS

    args.append('--tc-file={VENV}/%s' % CONFIG_FILE)
    if data.get('debug'):
        args.append('--tc=stages.enabled:1')
        tests = [os.path.join('{VENV}', x)
                 for x in re.split('\s+', (data.get('tests') or TESTS_DEBUG).strip())]
        args.extend(tests)
    else:
        args.append('--tc=stages.enabled:1')
        args.append('--eval-attr=rank > 0 and rank < 11')
        args.append('--with-email')
        args.append('--with-atom')
        # args.append('--with-bvtinfo')
        if not min_version_validator(params.build, params.version, params.hotfix,
                                     params.product, iso=data.content.build.iso,
                                     min_ver=CONFIG.global_min_supported):
            args.append('--with-atom-no-go=The requested product/version is not supported by this test suite.')

        args.append('--with-irack')
        # args.append('--with-qkview=never')
        # args.append('{VENV}/tests/solar/bvt/')
        args.append('{VENV}/%s' % CONFIG.paths.em)

    v = plugins.email.variables
    v.args = args
    v.project = data.content.build.branch.name
    v.version = data.content.build.version.version
    v.build = data.content.build.version.build
    LOG.info("ATOM EMBVT: Nose Args: " + str(args))
    LOG.info("ATOM EMBVT: our_config: " + str(our_config))

    result = nosetests.delay(our_config, args, data)  # @UndefinedVariable
    link = common_app.router.build('status', task_id=result.id)
    LOG.info("ATOM EMBVT: Status: " + str(result.status) + ", ID: " +
             str(result.id) + ", Link: " + str(link))
    embvt_result = dict(status=result.status, id=result.id, link=link)
    LOG.info("ATOM EMBVT: Result: " + str(embvt_result))
    return embvt_result


@app.get('/bvt/basic')
@app.get('/bigip_bvt_request')
@bottle.jinja2_view('bvt_basic', template_lookup=TEMPLATE_DIR)
def bvt_basic_view(task_id=None):
    return AttrDict(name='Hello world')
