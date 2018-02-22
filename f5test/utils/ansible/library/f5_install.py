#!/usr/bin/python

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: f5_install

short_description: Bridge to f5.ictester tool/

version_added: "2.4"

description:
    - "This is my longer description explaining my sample module"

options:
    name:
        description:
            - This is the message to send to the sample module
        required: true
    new:
        description:
            - Control to demo if the result of this module is changed or not
        required: false

extends_documentation_fragment:
    - azure

author:
    - Your Name (@yourhandle)
'''

EXAMPLES = '''
# Pass in a message
- name: Test with a message
  my_new_test_module:
    name: hello world

# pass in a message and have changed true
- name: Test with a message and changed output
  my_new_test_module:
    name: hello world
    new: true

# fail the module
- name: Test failure of the module
  my_new_test_module:
    name: fail me
'''

RETURN = '''
original_message:
    description: The original name param that was passed in
    type: str
message:
    description: The output message that the sample module generates
'''

from ansible.module_utils.basic import AnsibleModule
#from ansible.module_utils.my_cool_module import TEST
from f5test.macros.install import InstallSoftware
from f5test.base import Options
import logging

LOG = logging.getLogger(__name__)

def run_module():
    # define the available arguments/parameters that a user can pass to
    # the module
    module_args = dict(
        #name=dict(type='str', required=True),
        #new=dict(type='bool', required=False, default=False),
        address=dict(type='str', required=True),
        admin_username=dict(type='str', required=False),
        admin_password=dict(type='str', required=False, no_log=True),
        root_username=dict(type='str', required=False),
        root_password=dict(type='str', required=False, no_log=True),
        product=dict(type='str', required=True),
        version=dict(type='str', required=True),
        build=dict(type='str', required=False),
        hf=dict(type='str', required=False),
        essential=dict(type='bool', required=False, default=False),
        image=dict(type='str', required=False),
        hfimage=dict(type='str', required=False),
        timeout=dict(type='int', required=False, default=1200),
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=True,
        original_message='',
        message=''
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        return result

    options = Options()
    options.admin_username = module.params['admin_username']
    options.admin_password = module.params['admin_password']
    options.root_username = module.params['root_username']
    options.root_password = module.params['root_password']
    options.product = module.params['product']
    options.pversion = module.params['version']
    options.pbuild = module.params['build']
    options.phf = module.params['hf']
    options.essential_config = module.params['essential']
    options.image = module.params['image']
    options.hfimage = module.params['hfimage']
    options.timeout = module.params['timeout']
    address = module.params['address']

    level = logging.INFO
    LOG.setLevel(level)
    logging.basicConfig(level=level)

    cs = InstallSoftware(options=options, address=address)
    result['output'] = cs.run()

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
