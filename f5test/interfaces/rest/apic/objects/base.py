'''
Created on March 6, 2015
@author: jwong

'''
from .....base import AttrDict


class TaskError(Exception):
    pass


class DevFolder(AttrDict):
    class DevParam(AttrDict):
        def __init__(self, param):
            self.setdefault('@key', param['@key'])
            self.setdefault('@name', param['@name'])
            self.setdefault('@value', param['@value'])

    def __init__(self, *args, **kwargs):
        super(DevFolder, self).__init__(*args, **kwargs)
        self.setdefault('@key', '')
        self.setdefault('@name', '')
        self.setdefault('vnsDevParam', list())

    def add_param(self, param):
        """"""
        dev_param = self.DevParam(param)
        self.vnsDevParam.append(dev_param)


class Vns(object):
    URI = '/api/node/class/%s'

    def __init__(self, *args, **kwargs):
        super(Vns, self).__init__(*args, **kwargs)

    @staticmethod
    def get_vns(ifc, vns):
        r = ifc.api

        return r.get(Vns.URI % vns)
