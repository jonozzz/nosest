'''
Created on February 23, 2016

Contains helpers for generating test data, such as IP addresses, object names, etc.

@author: langer
'''
import random

from f5test.interfaces.testcase import ContextHelper
from f5test.macros.base import Macro


def ipv4_address_generator(first=None, second=None, third=1, fourth=1):
    """ Sequentially generate IP v4 addresses, skipping 255 in the
    3rd or 4th place.
    """
    max_value = 255
    if first is None:
        first = random.randint(10, 125)
    if second is None:
        second = random.randint(0, 255)

    while second <= max_value:
        yield '{0}.{1}.{2}.{3}'.format(first, second, third, fourth)

        if fourth >= max_value:
            fourth = 0
            third += 1
        else:
            fourth += 1

        if third > max_value:
            third = 0
            second += 1


def ipv6_address_generator(first=0xfd00, second=1, third=1, fourth=1):
    """ Sequentially generates IP v6 addresses."""
    max_value = 0xffff
    while second <= max_value:
        yield '{0}:{1}:{2}:{3}::'.format(hex(first).replace('0x', ''),
                                         hex(second).replace('0x', ''),
                                         hex(third).replace('0x', ''),
                                         hex(fourth).replace('0x', ''))

        if fourth >= max_value:
            fourth = 0
            third += 1
        else:
            fourth += 1

        if third > max_value:
            third = 0
            second += 1


generate_object_name = None
class GenerateObjectName(Macro):
    object_counter = 0

    def __init__(self, obj_type='Object', parent_id='name', *args, **kwargs):
        """
        Arguments are not necessary, but can help communicate information about the object at a glance.
        @param obj_type: Type of the object for which the name is being generated. e.g. 'Pool'
        @param parent_id: Unique identifier of the parent object, e.g. machineId, IP address, etc.
        @return: generated name
        """
        super(GenerateObjectName, self).__init__(*args, **kwargs)
        self.obj_type = obj_type
        self.parent_id = parent_id
        self.context = ContextHelper(__name__)
        self.session = self.context.get_config().get_session().name

    @classmethod
    def increment_counter(cls):
        cls.object_counter += 1

    def run(self):
        self.increment_counter()
        return '{0}-{1}-{2}-obj{3}'.format(self.obj_type, self.session, self.parent_id, self.object_counter)
