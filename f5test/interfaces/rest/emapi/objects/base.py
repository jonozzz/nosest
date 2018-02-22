import json

from .....base import enum, AttrDict
from ...base import BaseApiObject
from .....utils.wait import wait
from ...core import RestInterface

DEFAULT_TIMEOUT = 30


class TaskError(Exception):
    pass


class Reference(AttrDict):

    def __init__(self, other=None):
        if other:
            try:
                self['link'] = other['link'] if 'link' in other else other['selfLink']
            except KeyError:
                raise KeyError('Referenced object does not have a selfLink key.')

    def set(self, link):
        self['link'] = link


class ReferenceList(list):

    def __init__(self, other=None):
        super(ReferenceList, self).__init__()
        if other:
            map(self.append, other)

    def append(self, other):
        if not isinstance(other, Reference):
            other = Reference(other)
        return super(ReferenceList, self).append(other)

    def extend(self, others):
        return map(self.append, others)


class Link(AttrDict):
    def __init__(self, *args, **kwargs):
        super(Link, self).__init__(*args, **kwargs)
        self.setdefault('link', '')


class Task(BaseApiObject):
    STATUS = enum('CREATED', 'STARTED', 'CANCEL_REQUESTED', 'CANCELED',
                  'FAILED', 'FINISHED')
    PENDING_STATUSES = ('CREATED', 'STARTED', 'CANCEL_REQUESTED')
    FINAL_STATUSES = ('CANCELED', 'FAILED', 'FINISHED')
    FAIL_STATE = 'FAILED'

    @staticmethod
    def fail(message, resource):
        if resource.errorMessage:
            text = resource.errorMessage
        else:
            text = json.dumps(resource, sort_keys=True, indent=4,
                              ensure_ascii=False)
        raise TaskError("{}:\n{}".format(message, text))

    @staticmethod
    def wait(rest, resource, loop=None, timeout=30, interval=1,
             timeout_message=None):
        def get_status():
            return rest.get(resource.selfLink)
        if loop is None:
            loop = get_status
        ret = wait(loop, timeout=timeout, interval=interval,
                   timeout_message=timeout_message,
                   condition=lambda x: x.status not in Task.PENDING_STATUSES,
                   progress_cb=lambda x: 'Status: {0.status}:{0.currentStep}'.format(x))
        assert ret.status in Task.FINAL_STATUSES, "{0.status}:{0.error}".format(ret)

        if ret.status == Task.FAIL_STATE:
            Task.fail('Task failed', ret)

        return ret


#This is the BigIQ CM task. It can be used for ADC 5.0 and above, and security 4.6 and above
class CmTask(Task):
    BASE_URI = '/mgmt/cm/%s/tasks/%s'

    def wait(self, rstifc, resource, loop=None, timeout=DEFAULT_TIMEOUT,
             timeout_message=None):

        # Backwards compatibility
        rest = rstifc.api if isinstance(rstifc, RestInterface) else rstifc

        def get_status():
            return rest.get(resource.selfLink)
        if loop is None:
            loop = get_status

        wait(loop, timeout=timeout,
             timeout_message=timeout_message,
             condition=lambda x: x.status not in ('CREATED',),
             progress_cb=lambda x: 'Wait until out of CREATED state...')

        ret = wait(loop, timeout=timeout, interval=1,
                   timeout_message=timeout_message,
                   condition=lambda x: x.status not in ('STARTED', ),
                   progress_cb=lambda x: 'Status: {}:{}'.format(x.status,
                                                                x.currentStep))

#        temporarily lift the restriction on 'currentStep'. see bz 562848
#        if ret.status != 'FINISHED' or ret.currentStep not in ('DONE', ):
        if ret.status != 'FINISHED' or (ret.currentStep is not None and ret.currentStep not in ('DONE', )):
            Task.fail('Task failed', ret)


        return ret

