'''
Created on Jan 13, 2014

/mgmt/cm/asm workers

@author: mshah
'''
import datetime

from .....utils.mixins.profiling import BasicProfiler, BasicProfilerState
from .....utils.wait import wait
from ...base import BaseApiObject, AttrDict
from .base import Reference, ReferenceList, Task, DEFAULT_TIMEOUT


class AsmTask(Task):
    # This wait function is used in versions before Firestone.
    def wait(self, rest, resource, loop=None, *args, **kwargs):
        def get_status():
            return rest.get(resource.selfLink)
        if loop is None:
            loop = get_status
        ret = wait(loop,
                   condition=lambda x: x.overallStatus not in ('NEW',),
                   progress_cb=lambda x: 'Status: {0}'.format(x.overallStatus),
                   *args, **kwargs)
        assert ret.overallStatus == 'COMPLETED', "{0.overallStatus}:{0.status}".format(ret)
        return ret

    def wait_status(self, rest, resource, loop=None, check_no_pending_conflicts=False, *args, **kwargs):
        from dateutil.parser import parse

        if BasicProfiler.state == BasicProfilerState.enabled:
            BasicProfiler.state = BasicProfilerState.dont_save
        def get_status():
            return rest.get(resource.selfLink)
        if loop is None:
            loop = get_status
        ret = wait(loop,
                   condition=lambda x: x.status not in ('NEW', 'STARTED', 'PENDING_UPDATE_TASK'),
                   progress_cb=lambda x: 'Status: {0}'.format(x.status),
                   *args, **kwargs)

        if BasicProfiler.state == BasicProfilerState.dont_save:
            BasicProfiler.state = BasicProfilerState.enabled

        if "currentStep" in list(ret.keys()):
            pending_conflicts = 0
            if check_no_pending_conflicts and ret.currentStep in ('PENDING_CONFLICTS', 'PENDING_CHILD_CONFLICTS'):
                pending_conflicts = 1
            # Resolve 'PENDING_CONFLICTS' when the resolution to a conflict is 'NONE'.
            if ret.status == 'FINISHED' and ret.currentStep in ('PENDING_CONFLICTS', 'PENDING_CHILD_CONFLICTS'):
                for conflict in ret.conflicts:
                    if conflict.resolution == 'NONE':
                        conflict.resolution = "USE_BIGIQ"
                        payload = AttrDict()
                        payload.conflicts = [conflict]
                        payload.status = "STARTED"
                        resp = rest.patch(ret.selfLink, payload)
                        self.wait_status(rest, resp, interval=2, timeout=180,
                                         timeout_message="Patch PENDING_CONFLICTS timed out after {0}.")
                    else:
                        Task.fail('DMA has pending conflicts to resolve', ret)
            # Used in asm deploy
            elif ret.status == 'FINISHED' and ret.currentStep in ('DISTRIBUTE_CONFIG',):
                pass
            elif ret.status != 'FINISHED' or ret.currentStep != 'DONE':
                Task.fail("Either '%s' != 'FINISHED' or '%s' != 'DONE'"
                          % (ret.status, ret.currentStep), ret)
        else:
            if ret.status not in ('COMPLETED', 'FINISHED'):
                Task.fail("'%s' not in ('COMPLETED', 'FINISHED')"
                          % (ret.status,), ret)

        if BasicProfiler.state == BasicProfilerState.enabled:
            epoch = datetime.datetime.fromtimestamp(0)
            keys = {'startTime' : 'endTime', 'startDateTime' : 'endDateTime'}
            for start, end in keys.items():
                if ret.get(start) and ret.get(end):
                    BasicProfiler.save_result(resource.selfLink,
                                        req_type='_WAIT',
                                        start_time=(parse(ret.get(start)).replace(tzinfo=None) - epoch).total_seconds(),
                                        end_time=(parse(ret.get(end)).replace(tzinfo=None) - epoch).total_seconds())

        if check_no_pending_conflicts:
            return pending_conflicts == 0
        return ret

    def wait_canceled(self, rest, resource, loop=None, *args, **kwargs):
        def get_status():
            return rest.get(resource.selfLink)
        if loop is None:
            loop = get_status
        ret = wait(loop,
                   condition=lambda x: x.status not in ('CANCEL_REQUESTED',),
                   progress_cb=lambda x: 'Status: {0}'.format(x.status),
                   *args, **kwargs)
        assert ret.status == 'CANCELED', "{0.status}".format(ret)
        return ret


class DeployConfigTask(Task):
    URI = '/mgmt/cm/asm/tasks/deploy-configuration'

    def __init__(self, *args, **kwargs):
        super(DeployConfigTask, self).__init__(*args, **kwargs)
        self.setdefault('description', '')


class VirtualServerBase(BaseApiObject):
    def __init__(self, *args, **kwargs):
        super(VirtualServerBase, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('address', '')
        self.setdefault('fullPath', '')
        self.setdefault('isInactivePoliciesHolder', True)
        self.setdefault('deviceReference', Reference())
        self.setdefault('attachedPoliciesReferences', Reference())


# Used since 4.4.0; Abandoned starting from 4.5.0.
class VirtualServer(VirtualServerBase):
    URI = '/mgmt/cm/asm/virtual-servers'
    ITEM_URI = '/mgmt/cm/asm/virtual-servers/%s'

    def __init__(self, *args, **kwargs):
        super(VirtualServer, self).__init__(*args, **kwargs)


class VirtualServerV2(VirtualServerBase):
    URI = '/mgmt/cm/asm/working-config/virtual-servers'
    ITEM_URI = '/mgmt/cm/asm/working-config/virtual-servers/%s'

    def __init__(self, *args, **kwargs):
        super(VirtualServerV2, self).__init__(*args, **kwargs)


class PolicyBase(BaseApiObject):

    def __init__(self, *args, **kwargs):
        super(PolicyBase, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('id', '')
        self.setdefault('fullPath', '')
        self.setdefault('fileReference', Reference())
        self.setdefault('versionPolicyName', '')
        self.setdefault('versionDeviceName', '')
        self.setdefault('kind', '')
        self.setdefault('description', '')


class Policy(PolicyBase):
    URI = '/mgmt/cm/asm/policies'

    def __init__(self, *args, **kwargs):
        super(Policy, self).__init__(*args, **kwargs)


class PolicyV2(PolicyBase):
    URI = '/mgmt/cm/asm/working-config/policies'

    def __init__(self, *args, **kwargs):
        super(PolicyV2, self).__init__(*args, **kwargs)


class Violations(BaseApiObject):
    URI = '/mgmt/cm/asm/working-config/violations'

    def __init__(self, *args, **kwargs):
        super(Violations, self).__init__(*args, **kwargs)


class PolicyUpload(BaseApiObject):
    URI = '/mgmt/cm/asm/policy-files/upload/%s'

    def __init__(self, *args, **kwargs):
        super(PolicyUpload, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('id', '')
        self.setdefault('fullPath', '')
        self.setdefault('fileReference', Reference())
        self.setdefault('versionPolicyName', '')
        self.setdefault('versionDeviceName', '')
        self.setdefault('kind', '')
        self.setdefault('description', '')
        self.setdefault('srcType', '')


class PolicyDownload(BaseApiObject):
    URI = '/mgmt/cm/asm/policy-files/download/%s'

    def __init__(self, *args, **kwargs):
        super(PolicyDownload, self).__init__(*args, **kwargs)


# Used since 4.4.0; Abandoned starting from 4.5.0.
class VirtualPolicy(BaseApiObject):
    URI = '/mgmt/cm/asm/tasks/virtual-server-policy'

    def __init__(self, *args, **kwargs):
        super(VirtualPolicy, self).__init__(*args, **kwargs)
        self.setdefault('virtualServerId', '')
        self.setdefault('policyReference', Reference())
        self.setdefault('status', '')
        self.setdefault('overallStatus', '')
        self.setdefault('isResume', '')
        self.setdefault('isReset', '')


class GetDevice(BaseApiObject):
    URI = '/mgmt/shared/resolver/device-groups/cm-asm-allAsmDevices/devices'

    def __init__(self, *args, **kwargs):
        super(GetDevice, self).__init__(*args, **kwargs)
        self.setdefault('address', '')
        self.setdefault('state', '')
        self.setdefault('hostname', '')
        self.setdefault('version', '')
        self.setdefault('product', '')
        self.setdefault('build', '')


class RemoveMgmtAuthority(AsmTask):
    URI = '/mgmt/cm/asm/tasks/remove-mgmt-authority'

    def __init__(self, *args, **kwargs):
        super(RemoveMgmtAuthority, self).__init__(*args, **kwargs)
        self.setdefault('deviceReference', Reference())


class GetRemoveMgmtAuthority(BaseApiObject):
    URI = '/mgmt/cm/asm/tasks/remove-mgmt-authority/%s'

    def __init__(self, *args, **kwargs):
        super(RemoveMgmtAuthority, self).__init__(*args, **kwargs)
        self.setdefault('status', '')
        self.setdefault('deviceID', '')
        self.setdefault('deviceReference', Reference())


class DeclareMgmtAuthorityBase(AsmTask):
    URI = '/mgmt/cm/asm/tasks/declare-mgmt-authority'

    def __init__(self, *args, **kwargs):
        super(DeclareMgmtAuthorityBase, self).__init__(*args, **kwargs)
        self.setdefault('address', '')
        self.setdefault('overrideExistingPoliciesSrc', False)
        self.setdefault('automaticallyUpdateFramework', True)
        self.setdefault('rootUser', 'root')
        self.setdefault('rootPassword', 'default')


# Used since 4.4.0; Abandoned starting from 4.5.0.
class DeclareMgmtAuthority(DeclareMgmtAuthorityBase):
    def __init__(self, *args, **kwargs):
        super(DeclareMgmtAuthority, self).__init__(*args, **kwargs)
        self.setdefault('username', 'admin')
        self.setdefault('password', 'admin')
        self.setdefault('discoverSharedSecurity', False)


class DeclareMgmtAuthorityV2(DeclareMgmtAuthorityBase):
    def __init__(self, *args, **kwargs):
        super(DeclareMgmtAuthorityV2, self).__init__(*args, **kwargs)
        self.setdefault('deviceUsername', 'admin')
        self.setdefault('devicePassword', 'admin')
        self.setdefault('createChildTasks', True)
        self.setdefault('discoverSharedSecurity', True)


# Used since 4.4.0; Abandoned starting from 4.5.0.
class InactiveVirtualServerPolicy(AsmTask):
    URI = '/mgmt/cm/asm/tasks/inactive-virtual-server-policy'

    def __init__(self, *args, **kwargs):
        super(InactiveVirtualServerPolicy, self).__init__(*args, **kwargs)
        self.setdefault('policyReferences', ReferenceList())
        self.setdefault('virtualServerId', '')


class SignatureFileMetadata(BaseApiObject):
    URI = '/mgmt/cm/asm/signatures/repository/signature-files-metadata'
    ITEM_URI = '/mgmt/cm/asm/signatures/repository/signature-files-metadata/%s'

    def __init__(self, *args, **kwargs):
        super(SignatureFileMetadata, self).__init__(*args, **kwargs)
        self.setdefault('id', '')


class ScheduleUpdate(BaseApiObject):
    URI = '/mgmt/cm/asm/signatures/schedule-update'

    def __init__(self, *args, **kwargs):
        super(ScheduleUpdate, self).__init__(*args, **kwargs)
        self.setdefault('frequency', '')


class UpdatePushSignature(AsmTask):
    URI = '/mgmt/cm/asm/tasks/signatures/update-push-signatures'

    def __init__(self, *args, **kwargs):
        super(UpdatePushSignature, self).__init__(*args, **kwargs)


class Logging(BaseApiObject):
    URI = '/mgmt/cm/asm/logging'

    def __init__(self, *args, **kwargs):
        super(Logging, self).__init__(*args, **kwargs)
        self.setdefault('id', '')
        self.setdefault('isSuccessfull', '')


class DosProfile(BaseApiObject):
    URI = '/mgmt/cm/security-shared/working-config/dos-profiles'
    ITEM_URI = '/mgmt/cm/security-shared/working-config/dos-profiles/%s'

    def __init__(self, *args, **kwargs):
        super(DosProfile, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('partition', '')
        self.setdefault('fullPath', '')


class DosDeviceConfiguration(BaseApiObject):
    URI = '/mgmt/cm/security-shared/working-config/dos-device-config'

    def __init__(self, *args, **kwargs):
        super(DosDeviceConfiguration, self).__init__(*args, **kwargs)


class DosNetworkWhitelist(BaseApiObject):
    URI = '/mgmt/cm/security-shared/working-config/dos-network-whitelist'

    def __init__(self, *args, **kwargs):
        super(DosNetworkWhitelist, self).__init__(*args, **kwargs)


class SharedVirtualServers(BaseApiObject):
    URI = '/mgmt/cm/security-shared/working-config/virtuals'

    def __init__(self, *args, **kwargs):
        super(SharedVirtualServers, self).__init__(*args, **kwargs)


class CmAsmAllDevicesGroup(BaseApiObject):
    URI = '/mgmt/shared/resolver/device-groups/cm-asm-allDevices/devices'

    def __init__(self, *args, **kwargs):
        super(CmAsmAllDevicesGroup, self).__init__(*args, **kwargs)


class CmAsmAllAsmDevicesGroup(BaseApiObject):
    URI = '/mgmt/shared/resolver/device-groups/cm-asm-allAsmDevices/devices'

    def __init__(self, *args, **kwargs):
        super(CmAsmAllAsmDevicesGroup, self).__init__(*args, **kwargs)


class SignatureSets(BaseApiObject):
    URI = '/mgmt/cm/asm/working-config/signature-sets'

    def __init__(self, *args, **kwargs):
        super(SignatureSets, self).__init__(*args, **kwargs)
        self.setdefault('name', 'signature-set')
        self.setdefault('partition', 'Common')
        self.setdefault('noLock', False)
        self.setdefault('filter', AttrDict(accuracyFilter="all",
                                           accuracyValue="all",
                                           signatureType="all",
                                           userDefinedFilter="all",
                                           riskFilter="all",
                                           riskValue="all",
                                           lastUpdatedFilter="all",
                                           attackTypeReference=None))
        self.setdefault('isUserDefined', True)
        self.setdefault('assignToPolicyByDefault', False)
        self.setdefault('defaultAlarm', True)
        self.setdefault('defaultLearn', True)
        self.setdefault('defaultBlock', True)
        self.setdefault('systems', [])


# This URI valid only for 4.5.0 BIGIQs. URI have been changed in 4.5.0 HF2
class SignatureSetsBase(BaseApiObject):
    URI = '/mgmt/cm/asm/signature-sets'

    def __init__(self, *args, **kwargs):
        super(SignatureSetsBase, self).__init__(*args, **kwargs)


# This URI valid for 4.5.0, 4.5.0 HF2 BIGIQs. URI have been changed in 4.5.0 HF3
class Signatures(BaseApiObject):
    URI = '/mgmt/cm/asm/signatures/local-signatures'

    def __init__(self, *args, **kwargs):
        super(Signatures, self).__init__(*args, **kwargs)


# This URI valid for 4.5.0 HF3 BIGIQs
class SignaturesV2(BaseApiObject):
    URI = '/mgmt/cm/asm/working-config/signatures'

    def __init__(self, *args, **kwargs):
        super(SignaturesV2, self).__init__(*args, **kwargs)


class SignatureSystems(BaseApiObject):
    URI = '/mgmt/cm/asm/signature-systems'

    def __init__(self, *args, **kwargs):
        super(SignatureSystems, self).__init__(*args, **kwargs)


class AsmSnapshotConfigTask(AsmTask):
    URI = '/mgmt/cm/asm/tasks/snapshot-config'
    PENDING_STATES = ('STARTED')

    def __init__(self, *args, **kwargs):
        super(AsmSnapshotConfigTask, self).__init__(*args, **kwargs)
        self.setdefault('name', 'snapshot-config')
        self.setdefault('description', '')
        self.setdefault('subtasks', [])

    @staticmethod
    def wait(rest, snapshot, timeout=DEFAULT_TIMEOUT):
        selflink = snapshot.selfLink if isinstance(snapshot, dict) \
            else snapshot

        ret = wait(lambda: rest.get(selflink),
                   condition=lambda ret: ret.status not in AsmSnapshotConfigTask.PENDING_STATES,
                   progress_cb=lambda ret: 'Snapshot status: {0}'.format(ret.status),
                   timeout=timeout)

        if ret.status != 'FINISHED':
            Task.fail("SnapshotConfigTask failed", ret)

        return ret


class AsmSnapshotSubtask(AttrDict):
    def __init__(self, snapshot):
        super(AsmSnapshotSubtask, self).__init__(snapshot)
        self.setdefault('snapshot_reference', snapshot)


class AsmSnapshot(AttrDict):
    URI = '/mgmt/cm/asm/working-config/snapshots'

    def __init__(self, *args, **kwargs):
        super(AsmSnapshot, self).__init__(*args, **kwargs)
        self.setdefault('name', 'snapshot')
        self.setdefault('description', '')


class UpdatePolicySignature(BaseApiObject):
    URI = '/mgmt/cm/asm/working-config/policies/%s/signatures/update'

    def __init__(self, sig_reference, **kwargs):
        super(UpdatePolicySignature, self).__init__(sig_reference, **kwargs)
        self.setdefault('performStaging', True)
        self.setdefault('signatureReference', sig_reference)


class PolicyInheritanceUpdate(BaseApiObject):
    URI = '/mgmt/cm/asm/tasks/policy-inheritance-update'

    def __init__(self, child_ref, *args, **kwargs):
        super(PolicyInheritanceUpdate, self).__init__(*args, **kwargs)
        self.setdefault('childPolicyReference', child_ref)
        self.setdefault('action', 'detach')
        self.setdefault('parentPolicyReference', None)

class SectionsUpdate(BaseApiObject):
    URI = '/mgmt/cm/asm/tasks/sections-update'

    def __init__(self, *args, **kwargs):
        super(SectionsUpdate, self).__init__(*args, **kwargs)
        self.setdefault('sections', [])
