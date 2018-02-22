'''
Created on Aug 9, 2016

@author: dodrill
'''
import logging
from f5test.commands.rest.base import IcontrolRestCommand
from f5test.interfaces.rest.emapi.objects.storage import SecureStorageInterface
from f5test.utils.wait import wait_args

LOG = logging.getLogger(__name__)


set_secure_storage_master_key = None
class SetSecureStorageMasterKey(IcontrolRestCommand):  # @IgnorePep8
    """ Setup the Secure Storage Master key on the BIG-IQ.
    """
    def __init__(self, passphrase, *args, **kwargs):
        super(SetSecureStorageMasterKey, self).__init__(*args, **kwargs)
        self.passphrase = passphrase

    def setup(self):
        """ Create a simple POST body and send to the BIG-IQ to set the
            secure storage master key.  This can only be done once per
            BIG-IQ.

            Returns the response from the command.
        """
        LOG.info("Setting the BIG-IQ's secure storage master key...")
        payload = SecureStorageInterface(passphrase=self.passphrase)
        resp = None
        try:
            resp = self.api.post(SecureStorageInterface.URI, payload)
        except Exception, e:
            LOG.debug("BIG-IQ secure storage master key has already been set.")
            LOG.debug("Exception: " + str(e))
        return resp

is_secure_storage_master_key_set = None
class IsSecureStorageMasterKeySet(IcontrolRestCommand):  # @IgnorePep8
    """ Return whether or not the Secure Storage Master key has been set
        on the BIG-IQ.
    """
    def __init__(self, wait_for_it=False, timeout=60, *args, **kwargs):
        super(IsSecureStorageMasterKeySet, self).__init__(*args, **kwargs)
        self.wait_for_it = wait_for_it
        self.timeout = timeout

    def setup(self):
        """ Get the current status of the secure storage master key, and
            return if it is setup or not.
        """
        resp = self.api.get(SecureStorageInterface.URI)
        LOG.debug("Secure Storage Master Key Enabled Status: " + str(resp.isMkSet))
        return resp.isMkSet if not self.wait_for_it else wait_args(self.api.get, func_args=[SecureStorageInterface.URI],
                                                                   condition=lambda x: x.isMkSet is True,
                                                                   interval=5,
                                                                   timeout=self.timeout,
                                                                   timeout_message='Master Storage still not set after {0} seconds')
