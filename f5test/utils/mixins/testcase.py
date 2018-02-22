# Add your TestCase mixins here...
import os
import re
import sys
import time
import random
import logging
import collections
import f5test.commands.rest as RCMD
from f5test.interfaces.rest.emapi.objects.asm import CmAsmAllAsmDevicesGroup
from f5test.utils.wait import wait
from f5test.base import Options
from nose.plugins.skip import SkipTest


LOG = logging.getLogger(__name__)
CHECKLIST = 'checklist'

# for big-ip
URL_TM_DEVICE_INFO = "/mgmt/shared/identified-devices/config/device-info"

class AsmTestCase(object):

    def get_unique_tag(self):
        date = time.strftime("%Y%m%d")
        now = time.strftime("%H%M%S")
        process_id = os.getpid()
        random_int = ''.join(["%s" % random.randint(0, 9) for x in range(3)])  # 3 digits random number
        return "%s-%s-%s-%s" % (date, now, process_id, random_int)

    def remove_keys(self, dictionary, keys_to_remove):
        """Return a copy of dictionary with specified keys removed."""
        if not keys_to_remove:
            return dictionary

        d = dict(dictionary)
        for key in keys_to_remove:
            if key in d:
                del d[key]
        return d

    def assert_hash_equal(self, hash1, hash2, keys_to_remove=None, msg=None):
        # Remove the keys that is independant on hash1 and hash2
        hash1_truncated = self.remove_keys(hash1, keys_to_remove)
        hash2_truncated = self.remove_keys(hash2, keys_to_remove)

        # Assert parameters in hash1 and hash2 are the same
        self.maxDiff = None
        LOG.debug("==>expected:" + str(hash1_truncated))
        LOG.debug("==>actual:" + str(hash2_truncated))
        self.assertDictEqual(hash1_truncated, hash2_truncated, msg=msg)

    def assert_array_of_hashes_equal(self, expected, actual, primary_key, keys_to_remove=None, msg=None, strict=False):
        """This asserts that two array of hashes match each other.
        ex: both array has a hash that has the same description, "Illegal...",
        the following error msg means that, with the hash that has the same primary_key:
        1) hash of actual array doesn't have the missing key key1 which hash of expected array has.
        2) hash of actual array has addtional key key2 than hash of expected array.
        3) hash of actual array and hash of expected array have same key but diff values.

        [Hash with "description":"Illegal attachment in SOAP message"]
        [missing keys] "name":"key1"           <-- Doens't show in strict mode
        [additional keys] "name":"key2"        <-- Doens't show in strict mode
        [diff values] <key> violationReference
        [           ] <len diff> len_expected vs len_actual
        [           ] <expected val> {'link': 'https://localhost/mgmt/tm/asm/violations/tkmi0bSUBGtyF2frCc7ByA'}
        [           ] <actual val>   {'kind': 'cm:asm:working-config:violations:violationstate'...}
        """
        LOG.debug("==>expected:" + str(expected))
        LOG.debug("==>actual:" + str(actual))
        LOG.debug("primary_key's type:" + str(type(primary_key)) + "should eq <str>")
        LOG.debug("expected's type:" + str(type(expected)) + "should eq <list>")
        val_of_primary_key_list_expected = sorted([ hash[primary_key] for hash in expected ])
        val_of_primary_key_list_actual = sorted([ hash[primary_key] for hash in actual ])
        # Assert both array has the same number of hash and same primary key values
        self.assertEqual(val_of_primary_key_list_expected, val_of_primary_key_list_actual)

        OK = 1
        msg = "\n"
        for hash_e in expected:
            for hash_a in actual:
                if hash_e[primary_key] == hash_a[primary_key]:
                    fail_msg = '[Hash with "%s":"%s"]'\
                                 % (primary_key, hash_e[primary_key]) + "\n"
                    # Remove the keys that is independant on bigip and bigiq
                    hash_e = self.remove_keys(hash_e, keys_to_remove)
                    hash_a = self.remove_keys(hash_a, keys_to_remove)

                    # Compare if the hash with same pk value has same keys
                    # As hash keys compared here isn't huge, iterates through multiple times
                    same_keys = [key for key in hash_a.keys() if key in hash_e.keys()]
                    missing_keys = [key for key in hash_e.keys() if key not in hash_a.keys()]
                    additional_keys = [key for key in hash_a.keys() if key not in hash_e.keys()]
                    if missing_keys:
                        OK = 0 if strict else 1
                        missing_key_value_pair = [(key, hash_e[key]) for key in missing_keys]
                        for missing_key in missing_key_value_pair:
                            fail_msg += "[missing keys] " + \
                                        '"%s":"%s"' % (missing_key[0], missing_key[1]) + "\n"
                    if additional_keys:
                        OK = 0 if strict else 1
                        additional_key_value_pair = [(key, hash_a[key]) for key in additional_keys]
                        for additional_key in additional_key_value_pair:
                            fail_msg += "[additional keys] " + \
                                        '"%s":"%s"' % (additional_key[0], additional_key[1]) + "\n"

                    wrong_value_for_same_key = {}
                    for key in same_keys:
                        if isinstance(hash_e[key], list) and isinstance(hash_a[key], list):
                                hash_e[key] = [str(x) for x in hash_e[key]]
                                hash_a[key] = [str(x) for x in hash_a[key]]
                                if collections.Counter(hash_e[key]) != collections.Counter(hash_a[key]):
                                    OK = 0
                                    fail_msg += "%s,\nexpected:\n%s,\nactual:\n%s" % \
                                                (key, hash_e[key], hash_a[key])
                        elif hash_a[key] != hash_e[key]:
                            OK = 0
                            fail_msg += ("[diff values] (key) %s\n" % key
                                       + "              (len diff) expected %s vs actual %s\n" % (len(hash_e[key]), len(hash_a[key]))
                                       + "              (expected val) %s\n" % repr(hash_e[key])
                                       + "              (actual   val) %s\n" % repr(hash_a[key]))

                    # If this comparison fails, add fail msg to the msg stack
                    if OK == 0:
                        msg += fail_msg
        if OK == 0:
            self.fail(msg)

    def assertDictContainsSubsetWithList(self, expected, actual, msg=None):
        """Checks whether actual is a superset of expected."""
        missing = []
        mismatched = []
        for key, value in expected.iteritems():
            if key not in actual:
                missing.append(key)
            elif isinstance(value, list) and isinstance(actual[key], list):
                    value = [str(x) for x in value]
                    actual[key] = [str(x) for x in actual[key]]
                    if collections.Counter(value) != collections.Counter(actual[key]):
                        mismatched.append('%s,\nexpected:\n%s,\nactual:\n%s' %
                                          (key, value, actual[key]))
            elif value != actual[key]:
                mismatched.append('%s,\nexpected:\n%s,\nactual:\n%s' %
                                  (key, value, actual[key]))

        if not (missing or mismatched):
            return

        standardMsg = ''
        if missing:
            standardMsg = 'Missing: %s' % ','.join(safe_repr(m) for m in
                                                    missing)
        if mismatched:
            if standardMsg:
                standardMsg += '; '
            standardMsg += 'Mismatched values: %s' % ','.join(mismatched)

        if standardMsg != '':
            self.fail(standardMsg)


    def assert_two_elements_equal(self, element1, element2,
                            keys_to_remove=None, primary_key=None, msg=None):
        """Element could be either a hash or an array of hashes."""
        LOG.debug("==>keys_to_remove:" + str(keys_to_remove))
        LOG.debug("==>msg:" + str(msg))
        if len(element1) == 0 and len(element2) == 0:
            self.fail("Items are empty!")
        elif len(element1) == 1 and len(element2) == 1:
            LOG.info("calling assert_hash_equal()")
            self.assert_hash_equal(element1[0], element2[0],
                                   keys_to_remove=keys_to_remove,
                                   msg=msg)
        elif len(element1) >= 1 and len(element2) >= 1:
            LOG.info("calling assert_array_of_hashes_equal()")
            self.assert_array_of_hashes_equal(element1, element2,
                                        primary_key=primary_key,
                                        keys_to_remove=keys_to_remove,
                                        msg=msg)
        else:
            self.fail("Wrong element items: %s&%s" % (len(element1), len(element2)))

    def get_subcollectionReference_link(self, item_name, subcollection_name, response):
        """Return the subcollection reference link of a specified item and subcollection in a given response."""
        subcollectionReference_link = None
        for item in response["items"]:
            if item.name == item_name:
                subcollectionReference = subcollection_name + 'Reference'
                if subcollectionReference not in item:
                    self.fail("'%s' not found." % subcollectionReference)
                subcollectionReference_link = item.subcollectionReference.link
                break
        else:
            self.fail("'%s' not found." % item_name)
        return subcollectionReference



class SplitTestCase(object):
    """
    Provides a "checklist" dictionary as self.c that's shared between split phases.

    The assumption is that tests in both phases are named the same.
    """

    def setUp(self):
        super(SplitTestCase, self).setUp()
        name = re.sub('\.phase\d+.', '\._\.', self.id())
        cl = self.get_data(CHECKLIST)
        cl.setdefault(name, Options())
        self.c = cl[name]
        if self.c._has_failed:
            raise SkipTest('Test failed in preceding phase. Skipping.')

    def tearDown(self):
        try:
            self.c._has_failed = self.has_failed()
        finally:
            super(SplitTestCase, self).tearDown()

    def assertDictContainsSubset(self, expected, actual, msg=None, overlook=None):
        if overlook:
            expected = expected.copy()
            assert isinstance(overlook, (tuple, list))
            map(expected.pop, [x for x in overlook if x in expected])
        super(SplitTestCase, self).assertDictContainsSubset(expected, actual, msg)
