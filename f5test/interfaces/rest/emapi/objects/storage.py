'''
Created on Aug, 9, 2016

@author: dodrill
'''
from ...base import BaseApiObject


# Related to the Secure Storage REST API
class SecureStorageInterface(BaseApiObject):
    URI = '/mgmt/cm/shared/secure-storage/masterkey'

    def __init__(self, *args, **kwargs):
        super(SecureStorageInterface, self).__init__(*args, **kwargs)
        self.setdefault('passphrase', '')

