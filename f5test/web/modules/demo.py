'''
Created on Mar 13, 2017

@author: jono
'''
import bottle
import logging
import json
import yaml
import re


from f5test.base import AttrDict
from ..tasks import add, nosetests
from .common import (app as common_app, TEMPLATE_DIR, get_harness, CONFIG,
                     NOSETESTS_ARGS)
from ..validators import min_version_validator


app = bottle.Bottle()
LOG = logging.getLogger(__name__)


# curl -d '{"number_1": 1, "number_2": 3}' -H 'Content-Type: application/json' http://localhost:8081/add
@app.post('/add')
def add_post():
    LOG.info("ADD: called")
    data = AttrDict(bottle.request.json)
    result = add.delay(data.number_1 or 0, data.number_2 or 0, user_input=data)  # @UndefinedVariable
    link = common_app.router.build('status', task_id=result.id)
    add_result = dict(status=result.status, id=result.id, link=link)
    LOG.info("ADD: Result: " + str(add_result))
    return add_result


@app.get('/add')
@bottle.jinja2_view('add', template_lookup=TEMPLATE_DIR)
def add_view(task_id=None):
    return AttrDict(name='Hello world')


@app.post('/deobfuscator')
def simple_decrypter_post():
    LOG.info("DEOBFUSCATOR: Called")
    from Crypto.Cipher import DES
    from base64 import b64decode
    unpad = lambda s: s[0:-ord(s[-1])]  # @IgnorePep8
    data = AttrDict(bottle.request.json)
    try:
        i = data.input.decode('unicode_escape')
        ret = unpad(DES.new('GhVJDUfx').decrypt(b64decode(i)))
    except Exception, e:
        result = dict(input=str(e))
        LOG.info("DEOBFUSCATOR: Exception when decoding: " + str(result))
        return result
    result = dict(input=ret)
    LOG.info("DEOBFUSCATOR: Result: " + str(result))
    return result


@app.get('/deobfuscator')
@bottle.jinja2_view('deobfuscator', template_lookup=TEMPLATE_DIR)
def simple_decrypter_view():
    return AttrDict(name='Hello world')


@app.route('/bvt_test', method='POST')
def bvt_test_post():
    """Handles requests from BIGIP teams for BIGIQ BVT, all modules except
        ASM.

    All the logic needed to translate the user input into what makes sense to
    us happens right here.
    """
    LOG.info("BIG-IQ CM: Called")
    BVTINFO_PROJECT_PATTERN = '(\D+)?(\d+\.\d+\.\d+)-?(eng-?\w*|hf\d+|hf-\w+)?'

    # For people who don't like to set the application/json header.
    print bottle.request.body.read()
    data = AttrDict(json.load(bottle.request.body))
    LOG.info("BIG-IQ CM POST Request: " + str(data))
    data._referer = bottle.request.url

    CONFIG_FILE = 'config/web_request_demo.yaml'
    our_config = AttrDict(yaml.load(open(CONFIG_FILE).read()))

    if data.get('devices'):
        our_config.update({'devices': data['devices']})

    # Prepare placeholders in our config
    our_config.update({'stages': {'main': {'setup': {'install-bigips': {'parameters': {}}}}}})
    our_config.update({'plugins': {'email': {'to': [], 'variables': {}}}})
    our_config.update({'plugins': {'json_reporter': {}}})
    #our_config.update({'plugins': {'bvtinfo': {'bigip': {}}}})
    tests = data.get('tests', [CONFIG.paths.default])

    #LOG.info(tests)

    plugins = our_config.plugins
    # Set BVTInfo data
    #plugins.bvtinfo.project = data['project']
    #plugins.bvtinfo.build = data['build']
    #plugins.bvtinfo.bigip.name = 'bigiq-bvt'
    plugins.json_reporter['callback url'] = data.get('endpoint')

    # Append submitter's email to recipient list
    if data.get('submitted_by'):
        plugins.email.to.append(data['submitted_by'])
    plugins.email.to.extend(CONFIG.web.recipients)

    # Set version and build in the install stage
#     params = our_config.stages.main.setup['install-bigips'].parameters
#     match = re.match(BVTINFO_PROJECT_PATTERN, data['project'])
#     if match:
#         params['version'] = match.group(2)
#         if match.group(3):
#             params['hotfix'] = match.group(3)
#     else:
#         params['version'] = data['project']
#     params['build'] = data['build']
#     params['custom iso'] = data.get('custom_iso')
#     params['custom hf iso'] = data.get('custom_hf_iso')
#     params.product = 'bigip'
# 
#     if not min_version_validator(params.build, params.version, params.hotfix,
#                                  params.product, min_ver=CONFIG.supported):
#         # raise ValueError('Requested version not supported')
#         bottle.response.status = 406
#         return dict(message='Requested version not supported')

    args = []
    args[:] = NOSETESTS_ARGS

    args.append('--tc-file={VENV}/%s' % CONFIG_FILE)
    #args.append('--tc=stages.enabled:1')
    # For chuckanut++
    #args.append('--eval-attr=rank >= 1 and rank <= 10')
    #args.append('--with-email')
    # args.append('--with-bvtinfo')
    args.append('--with-irack')
    args.append('--with-jsonreport')
    args.append('--with-qkview=never')
    args.extend('{VENV}/%s' % x for x in tests)

    v = plugins.email.variables
    v.args = args
#     v.project = data['project']
#     v.version = params.version
#     v.build = params.build
    LOG.info("BIG-IQ CM Nose Args: " + str(v))
    LOG.info("BIG-IQ CM ourconfig: " + str(our_config))

    # return dict(config=our_config, args=args)
    result = nosetests.delay(our_config, args, data)  # @UndefinedVariable
    #result = AttrDict(id='1234', status="OK")
    link = common_app.router.build('status', task_id=result.id)
    cm_result = dict(status=result.status, id=result.id, link=link)
    LOG.info("BIG-IQ CM Result: " + str(cm_result))
    return cm_result
