'''
Created on April 8, 2016

@author: slu
'''
import logging
from f5test.utils.wait import wait

LOG = logging.getLogger(__name__)

def open_file_safe(filepath, timeout=30):
    '''Workaround for BZ585092. Check if file can be opened before returning the file object.

    Args:
        filepath (str): The path of the file to be opened

    Returns:
        file: The file object from f.open()

    '''

    def try_open():
        f = open(filepath)
        LOG.info("File at %s opened." % filepath)
        return f

    f = wait(try_open,
            timeout=timeout,
            timeout_message="File not found after {0}s.")

    return f
