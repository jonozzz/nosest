'''
Created on Dec 17, 2014

@author: xiaotian
'''
import base64
import logging
import re

from f5test.base import AttrDict
from f5test.commands.base import CommandError
from f5test.commands.rest.base import IcontrolRestCommand
from f5test.interfaces.rest.emapi import EmapiResourceError
from f5test.interfaces.rest.emapi.objects.adccore import WorkingLtmVip
from f5test.interfaces.rest.emapi.objects.asm import AsmTask
from f5test.interfaces.rest.emapi.objects import NetworkSelfip
from f5test.utils.systemio import open_file_safe
from f5test.utils.wait import wait

#for big-ip
URL_TM_LTM_VIRTUAL         = "/mgmt/tm/ltm/virtual"
URL_TM_LTM_POLICY          = "/mgmt/tm/ltm/policy"
URL_TM_ASM_IMPORT_POLICY   = "/mgmt/tm/asm/tasks/import-policy"
URL_TM_ASM_APPLY_POLICY    = "/mgmt/tm/asm/tasks/apply-policy"
URL_TM_ASM_POLICIES        = "/mgmt/tm/asm/policies"
URL_TM_ASM_EVENTS_REQUESTS = "/mgmt/tm/asm/events/requests"
URL_TM_LOG_PROFILE         = "/mgmt/tm/security/log/profile"

# for big-iq
URL_CM_ASM_VIRTUALS = "/mgmt/cm/asm/working-config/virtual-servers"
URL_CM_ASM_SIGNATURE_FILE_UPLOAD =  "/mgmt/cm/asm/signatures/repository/signature-files/upload/%s"
URL_CM_ASM_POLICIES = "/mgmt/cm/asm/working-config/policies"
URL_CM_ASM_SIGNATURES = "/mgmt/cm/asm/working-config/signatures"
URL_CM_ASM_SIGNATURESETS = "/mgmt/cm/asm/working-config/signature-sets"
URL_CM_ASM_SIGNATURESYSTEMS = "/mgmt/cm/asm/signature-systems"
URL_CM_ASM_ATTACKTYPE = "/mgmt/cm/asm/attack-types/"

LOG = logging.getLogger(__name__)


get_self_ip= None
class GetSelfIp(IcontrolRestCommand):  # @IgnorePep8
    """Get the first self ip of the given device.

    Predefine:
        from f5test.interfaces.rest.emapi.objects import NetworkSelfip

    Args:
        vlan_name (str): The vlan name for the self ip. Defaults to "internal".
        ipv6 (boolean): Select ipv6 self ip if true. Defaults to False.

    Returns:
        str: the first device's self ip that matches vlan_name and ip format.

    """
    def __init__(self, vlan_name="internal", ipv6=False, *args, **kwargs):
        super(GetSelfIp, self).__init__(*args, **kwargs)
        self.vlan_name = vlan_name
        self.ipv6 = ipv6

    def setup(self):
        delimiter = '.' if not self.ipv6 else ':'
        resp = self.api.get(NetworkSelfip.URI)
        for item in resp["items"]:
            # select selfip with selected vlan name
            resp = self.api.get(item.vlanReference.link)
            if resp.name == self.vlan_name:
                # select selfip with selected ip format
                if delimiter in item.address:
                    self_ip = item.address.split('/')[0]
                    break
        else:
            raise CommandError("Didn't find correct self ip with vlan '{0}', delimiter '{1}' in: {2}"
                               .format(self.vlan_name, delimiter, resp))
        return self_ip


create_virtual_server = None
class CreateVirtualServer(IcontrolRestCommand):  # @IgnorePep8
    """Create a virtual on a given bigip.

    Predine:
        URL_TM_LTM_VIRTUAL = "/mgmt/tm/ltm/virtual"

    Args:
        name (str): The name of virtual server.
        destination(str): The destination address of virtual server.
           eg. 1.2.3.4:80
        *args, **kwargs: virtual's specific attibutes.
            eg. kwarg "partition" defaults to "Common";
                kwarg "profiles" defaults to ["tcp", "http", "websecurity"].

    Returns:
         AttrDict: The whole state of virtual created.

    """
    def __init__(self, name, destination, *args, **kwargs):
        super(CreateVirtualServer, self).__init__(*args, **kwargs)
        self.name = name
        self.destination = destination
        self.partition = kwargs.get("partition", "Common")
        self.profiles = kwargs.get("profiles", ["tcp", "http", "websecurity"])

    def setup(self):
        payload = AttrDict()
        payload.name = self.name
        payload.destination = self.destination
        payload.partition = self.partition
        payload.profiles = []
        for profile_name in self.profiles:
            profile = AttrDict()
            profile.name = profile_name
            payload.profiles.append(profile)
        try:
            resp = self.api.post(URL_TM_LTM_VIRTUAL, payload)
        except EmapiResourceError as e:
            if 'illegally shares destination address' in e.msg:
                ret = self.api.get(URL_TM_LTM_VIRTUAL)
                for item in ret["items"]:
                    if item.destination.endswith(self.destination) \
                        and item.partition == self.partition:
                            self.api.delete(item.selfLink)
                resp = self.api.post(URL_TM_LTM_VIRTUAL, payload)
            else:
                raise CommandError("Unexpected error: %s" % e.msg)
        return resp


import_asm_policy = None
class ImportAsmPolicy(IcontrolRestCommand):  # @IgnorePep8
    """Import/create an asm policy on a given bigip.

    Predefine:
        import base64
        from f5test.interfaces.rest.emapi.objects.asm import AsmTask
        URL_TM_ASM_IMPORT_POLICY = "/mgmt/tm/asm/tasks/import-policy"

    Args:
        name (str): The policy's name.
        file_path (str): The path of policy file.

    Returns:
        AttrDict: The whole state of policy imported.

    """
    def __init__(self, name, file_path, *args, **kwargs):
        super(ImportAsmPolicy, self).__init__(*args, **kwargs)
        self.name = name
        self.file_path = file_path

    def setup(self):
        # Read policy file
        LOG.info('importing asm policy from file: %s' % self.file_path)
        f = open_file_safe(self.file_path)
        policy_body = f.read()
        # Encoded policy file with base64 algorithm
        policy_body = base64.b64encode(policy_body)

        # POST/import the policy to device
        payload = AttrDict()
        payload.file = policy_body
        payload.name = self.name
        payload.isBase64 = True
        resp = self.api.post(URL_TM_ASM_IMPORT_POLICY, payload)
        # Policy can only be deleted after it's deactived and deassociated from ltm virtual,
        # thus delete its selflink in assign_asm_policy_to_virtual
        AsmTask().wait_status(self.api, resp, interval=2, timeout=180,
                              timeout_message="Import policy timed out after {0}, "\
                                              "last status is {1.status}, "\
                                              "result is \"{1.result}\"")
        resp = self.api.get(resp.selfLink)
        policy_selflink = resp.result.policyReference.link
        resp  = self.api.get(policy_selflink)
        return resp


apply_asm_policy = None
class ApplyAsmPolicy(IcontrolRestCommand):  # @IgnorePep8
    """Activate/apply an asm policy on a given device.

    Predefine:
        from f5test.interfaces.rest.emapi.objects.asm import AsmTask
        URL_TM_ASM_APPLY_POLICY = "/mgmt/tm/asm/tasks/apply-policy"

    Args:
        policy (AttrDict): The whole state of the policy.

    Returns:
        AttrDict: The whole state of apply-policy.

    """
    def __init__(self, policy, *args, **kwargs):
        super(ApplyAsmPolicy, self).__init__(*args, **kwargs)
        self.policy = policy

    def setup(self):
        # POST/apply the policy
        payload = AttrDict()
        policy_reference = AttrDict()
        policy_reference.link = self.policy.selfLink
        payload.policyReference = policy_reference
        resp = self.api.post(URL_TM_ASM_APPLY_POLICY, payload)
        AsmTask().wait_status(self.api, resp, interval=2, timeout=180,
                              timeout_message="Apply policy timed out after {0}, "\
                                              "last status is {1.status}")
        ret = resp

# TODO: put in test
#        LOG.info("Putting response of apply_policy into self.garbage_bigip")
#        self.garbage_bigip[device].append(resp)

        # PATCH/patch the policy to make sure log daemon catch the right mapping
        # workround to BZ488306
        payload = AttrDict()
        payload.description = "This is a description"
        resp = self.api.patch(self.policy.selfLink, payload)

        return ret


assign_asm_policy_to_virtual = None
class AssignAsmPolicyToVirtual(IcontrolRestCommand):  # @IgnorePep8
    """Assign an asm policy to a given virtual server on bigip.

    Predefine:
        URL_TM_LTM_POLICY = "/mgmt/tm/ltm/policy"

    Args:
        policy (AttrDict): The whole state of the policy object.
        virtual (AttrDict): The whole state of the virtual object.

    Returns:
        AttrDict: The whole state of policy with virtual attached.

    """
    def __init__(self, policy, virtual, *args, **kwargs):
        super(AssignAsmPolicyToVirtual, self).__init__(*args, **kwargs)
        self.policy = policy
        self.virtual = virtual

    def setup(self):
        # PATCH/patch to policy with virtual server's name
        payload = AttrDict()
        payload.virtualServers = []
        payload.virtualServers.append(self.virtual.fullPath)
        resp = self.api.patch(self.policy.selfLink, payload)

# TODO: put in test
#        # ltm policy needs to be deleted/deactived first
#        path = URL_TM_LTM_POLICY + "/~Common~asm_auto_l7_policy__%s" % virtual.name
#        ltm_activated_policy = api.get(path)
#        LOG.info("Putting ltm_activated_policy into self.garbage_bigip")
#        self.garbage_bigip[device].append(ltm_activated_policy)
#
#        # asm policy needs to be deleted after ltm policy's deletion
#        LOG.info("Putting attach_virtual_to_policy into self.garbage_bigip")
#        self.garbage_bigip[device].append(resp)

        return resp


# TODO: set default values
create_logging_profile = None
class CreateLoggingProfile(IcontrolRestCommand):  # @IgnorePep8
    """Create a logging profile on bigip.

    Predefine:
        URL_TM_LOG_PROFILE = "/mgmt/tm/security/log/profile"

    Args:
        logging_profile_name (str): The name of logging profile.
        logging_bigiqs (list): A list og logging bigiq (DeviceAccess).

    Returns:
        AttrDict: The whole state of logging profile created.
    """
    def __init__(self, logging_profile_name, logging_bigiqs=None, *args, **kwargs):
        super(CreateLoggingProfile, self).__init__(*args, **kwargs)
        self.logging_profile_name = logging_profile_name
        self.logging_bigiqs = logging_bigiqs

    def setup(self):
        #create a logging profile pointing to logging bigiq
        payload = AttrDict()
        payload.name = self.logging_profile_name
        payload.application = AttrDict()
        payload.application[self.logging_profile_name] = AttrDict()
        payload_log_profile = payload.application[self.logging_profile_name]
        payload_log_profile.format = AttrDict()
        payload_log_profile.format.type = "user-defined"
        payload_log_profile.format.userString = ("unit_hostname=\\\"%unit_hostname%\\\",management_ip_address="
            +"\\\"%management_ip_address%\\\",http_class_name=\\\"%http_class_name%\\\",web_application_name=\\\"%http_class_name%"
            +"\\\",policy_name=\\\"%policy_name%\\\",policy_apply_date=\\\"%policy_apply_date%\\\",violations=\\\"%violations%\\\","
            +"support_id=\\\"%support_id%\\\",request_status=\\\"%request_status%\\\",response_code=\\\"%response_code%\\\",ip_client="
            +"\\\"%ip_client%\\\",route_domain=\\\"%route_domain%\\\",method=\\\"%method%\\\",protocol=\\\"%protocol%\\\",query_string="
            +"\\\"%query_string%\\\",x_forwarded_for_header_value=\\\"%x_forwarded_for_header_value%\\\",sig_ids=\\\"%sig_ids%\\\",sig_names="
            +"\\\"%sig_names%\\\",date_time=\\\"%date_time%\\\",severity=\\\"%severity%\\\",attack_type=\\\"%attack_type%\\\",geo_location="
            +"\\\"%geo_location%\\\",ip_address_intelligence=\\\"%ip_address_intelligence%\\\",username=\\\"%username%\\\",session_id="
            +"\\\"%session_id%\\\",src_port=\\\"%src_port%\\\",dest_port=\\\"%dest_port%\\\",dest_ip=\\\"%dest_ip%\\\",sub_violations="
            +"\\\"%sub_violations%\\\",virus_name=\\\"%virus_name%\\\",uri=\\\"%uri%\\\",request=\\\"%request%\\\",violation_details="
            +"\\\"%violation_details%\\\",header=\\\"%headers%\\\",response=\\\"%response%\\\"")
        payload_log_profile.guaranteeLogging = "enabled"
        payload_log_profile.guaranteeResponseLogging = "enabled"
        payload_log_profile.localStorage = "enabled"
        payload_log_profile.logicOperation= "and"
        payload_log_profile.maximumEntryLength= "64k"
        payload_log_profile.maximumHeaderSize= "any"
        payload_log_profile.maximumQuerySize= "any"
        payload_log_profile.maximumRequestSize = "any"
        payload_log_profile.protocol = "tcp"
        payload_log_profile.remoteStorage = "remote"
        payload_log_profile.reportAnomalies = "disabled"
        payload_log_profile.responseLogging = "all"
        payload_log_profile.filter = []
        filter_hash = AttrDict()
        filter_hash.name = "request-type"
        filter_hash.values = ["all"]
        payload_log_profile.filter.append(filter_hash)
        filter_hash = AttrDict()
        filter_hash.name = "search-all"
        payload_log_profile.filter.append(filter_hash)
        payload_log_profile.servers = []
        server = AttrDict()
        server.name = "%s:8514" % self.logging_bigiqs[0].get_address()
        payload_log_profile.servers.append(server)

        resp = self.api.post(URL_TM_LOG_PROFILE, payload)
        return resp


assign_logging_profile_to_virtual = None
class AssignLoggingProfileToVirtual(IcontrolRestCommand):  # @IgnorePep8
    """Assign a logging profile to a given virtual server on bigip.

    Args:
        logging_profile_name (str): The name of logging profile.
        virtual (AttrDict): The whole state of the virtual object.

    Returns:
        AttrDict: The whole state of virtual with logging profile attached.

    """
    def __init__(self, logging_profile_name, virtual, *args, **kwargs):
        super(AssignLoggingProfileToVirtual, self).__init__(*args, **kwargs)
        self.logging_profile_name = logging_profile_name
        self.virtual = virtual

    def setup(self):
        # PATCH/patch the logging profile to the virtual server
        payload = AttrDict()
        payload.securityLogProfiles= []
        payload.securityLogProfiles.append(self.logging_profile_name)
        resp = self.api.patch(self.virtual.selfLink, payload)
        return resp

show_evaluation_diff = None
class ShowEvaluationDiff(IcontrolRestCommand):  # @IgnorePep8
    """Show diffs of an deploy evaluation task.

    Args:
        resp (AttrDict): The whole state of the deploy task.

    Returns:
        str: diffs of evalution.

    """
    def __init__(self, task, *args, **kwargs):
        super(ShowEvaluationDiff, self).__init__(*args, **kwargs)
        self.task = task
        self.diff = ''

    def setup(self):
        self.diff = '\n=Evaluation Diffs=\n'
        resp = self.api.get(self.task.differenceReference.link)
        deviceDiffs = None
        if 'differencePartsCollectionReference' in resp:
            # takes effects after 5.0.0 (including Greenflash)
            deviceDiffs = self.api.get(resp.differencePartsCollectionReference.link)['items']
        else:
            # used before 5.0.0 (not including Greenflash)
            deviceDiffs = resp.deviceDifferences
        for deviceDiff in deviceDiffs:
            resp = self.api.get(deviceDiff.deviceReference.link)
            self.diff += "==device== %s(%s)\n" % (resp.hostname, resp.address)
            self.diff += "==parsed from endpoint== %s\n" % deviceDiff.selfLink
            self.diff_helper(deviceDiff, 0) # recursively adding config diffs
        return self.diff

    def diff_helper(self, deviceDiff, nestedLevel):
        """ Adding device config diffs to self.diff recursively.
            ref: bigiq-mgmt-cm/f5app/em_rest_java/src/com/f5/rest/workers/configmgmtbase/task/difference/SummaryHelper.java
        Args:
            deviceDiff (dict): resp of "/mgmt/cm/asm/config-differences/<uuid>/parts/<uuid>"
            nestedLevel (int): nested level
        """
        for item in deviceDiff.get('added', []):
            self.diff += "=== added ===(lvl: %s)\n" % nestedLevel
            self.diff += "toRef: %s\n" % self.api.get(item.toReference.link)
            if 'nestedDifferences' in item:
                nestedLevel += 1
                self.diff_helper(item.nestedDifferences, nestedLevel)

        for item in deviceDiff.get('changed', []):
            self.diff += "===changed===(lvl: %s)\n" % nestedLevel
            fromRef = self.api.get(item.fromReference.link)
            toRef = self.api.get(item.toReference.link)
            self.diff += "fromRef: %s\n" % fromRef
            self.diff += "toRef:   %s\n" % toRef
            # == workaround for bug 572346 ==
            m_fromRef = re.search(r'bruteForceProtectionForAllLoginPages', str(fromRef))
            m_toRef = re.search(r'bruteForceProtectionForAllLoginPages', str(toRef))
            if m_fromRef and m_toRef \
                and str(fromRef)[m_fromRef.end() + 3] != str(toRef)[m_toRef.end() + 3]: # T != F
                    self.diff += "(bug 572346) Potential false diff due to 'bruteForceProtectionForAllLoginPages' diff: %s != %s\n" \
                                  % (str(fromRef)[m_fromRef.end() + 3], str(toRef)[m_toRef.end() + 3])
            # ===============================

            if 'nestedDifferences' in item:
                nestedLevel += 1
                self.diff_helper(item.nestedDifferences, nestedLevel)

        for item in deviceDiff.get('removed', []):
            self.diff += "===removed===(lvl: %s)\n" % nestedLevel
            self.diff += "fromRef: %s\n" % self.api.get(item.fromReference.link)
            if 'nestedDifferences' in item:
                nestedLevel += 1
                self.diff_helper(item.nestedDifferences, nestedLevel)


delete_virtuals = None
class DeleteVirtuals(IcontrolRestCommand):
    """Deletes all virtuals given a name on BIGIQ.

    Args:
        name (str): The name of the virtual server.
        match (str): The type of match to be done with the name argument.
            Can be 'exact', 'contains', 'startswith', or 'endswith.
    Returns:
        None
    """

    def __init__(self, name, match='exact', *args, **kwargs):
        super(DeleteVirtuals, self).__init__(*args, **kwargs)
        self.name = name
        self.virtuals = []
        if match in ['exact', 'contains', 'startswith', 'endswith']:
            self.match = match
        else:
            raise ValueError(
                "delete_virtuals 'match' must be one of ['exact', 'contains', 'starts_with', 'ends_with']")

    def poll_virtuals_empty(self):
        for virtual in self.api.get(URL_CM_ASM_VIRTUALS)["items"]:
            if virtual.name in self.virtuals:
                return False
        return True

    def setup(self):
        for virtual in self.api.get(WorkingLtmVip.URI)["items"]:
            if self.match == 'exact':
                if self.name == virtual.name:
                    self.virtuals.append(virtual.name)
                    self.api.delete(virtual.selfLink)
            elif self.match == 'contains':
                if self.name in virtual.name:
                    self.virtuals.append(virtual.name)
                    self.api.delete(virtual.selfLink)
            elif self.match == 'startswith':
                if virtual.name.startswith(self.name):
                    self.virtuals.append(virtual.name)
                    self.api.delete(virtual.selfLink)
            elif self.match == 'endswith':
                if virtual.name.endswith(self.name):
                    self.virtuals.append(virtual.name)
                    self.api.delete(virtual.selfLink)

        LOG.info("Ensure virtual servers no longer exist in ASM")
        wait(self.poll_virtuals_empty, interval=2, timeout=10,
             timeout_message="Virtual servers were not removed from bigiq in {0}s.")
