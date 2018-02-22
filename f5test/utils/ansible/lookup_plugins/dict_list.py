# (c) 2014, Kent R. Spillner <kspillner@acm.org>
# (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = """
    lookup: dict_list
    version_added: "2.4"
    short_description: returns key/value pair items from a dictionary of lists
    description:
        - Takes a dictionary as input and returns a list with each item in the list being a dictionary with 'key' and 'value' as
          keys to the previous dictionary's structure.
    options:
        _raw:
            description:
                - A dictionary with all values iterable
            required: True
"""

EXAMPLES = """
tasks:
  - name: show dictionary
    debug: msg="{{item.key}}: {{item.value}}"
    with_dict_list: {a: [1, 2, 3], b: [3, 4, 5]}

# with predefined vars
vars:
  users:
    alice:
      - name: Alice Appleworth
        telephone: 123-456-7890
    bob:
      - name: Bob Bananarama
        telephone: 987-654-3210
tasks:
  - name: Print phone records
    debug:
      msg: "User {{ item.key }} is {{ item.value.name }} ({{ item.value.telephone }})"
    with_dict_list: "{{ users }}"
"""

RETURN = """
  _list:
    description:
      - list of composed dictonaries with key and value
    type: list
"""
import collections

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase


class LookupModule(LookupBase):

    @staticmethod
    def _flatten_hash_to_list(terms):
        ret = []
        for key in terms:
            if not isinstance(terms, collections.Iterable):
                raise AnsibleError("with_dict_list expects lists as values")
            for value in terms[key]:
                ret.append({'key': key, 'value': value})
        return ret

    def run(self, terms, variables=None, **kwargs):

        # Expect any type of Mapping, notably hostvars
        if not isinstance(terms, collections.Mapping):
            raise AnsibleError("with_dict_list expects a dict")

        return self._flatten_hash_to_list(terms)
