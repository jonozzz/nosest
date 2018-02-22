'''
Created on Jan 21, 2012

@author: jono
'''
from ..base import SeleniumCommand
from ....interfaces.selenium.driver import By
from ..common import browse_to, wait_for_loading, browse_to_tab
from .tasks import wait_for_task
import logging

LOG = logging.getLogger(__name__)


sync_to = None
class SyncTo(SeleniumCommand): #@IgnorePep8
    """Sync To Peer or Group."""

    def setup(self):
        b = self.api

        v = self.ifc.version
        success = True
        if v.product.is_em and v < 'em 3.0':
            browse_to('System | High Availability | ConfigSync', ifc=self.ifc)
            button = b.wait('SYNC_PUSH', frame='/contentframe')

            button.click()
            alert = b.switch_to_alert()
            alert.accept()
            LOG.info('Syncing...')
            wait_for_loading(ifc=self.ifc)
            success = not wait_for_task(timeout=600, ifc=self.ifc)
        elif v.product.is_em and v < 'em 3.1':
            checked_dgs = set([])
            while True:
                browse_to('Device Management | Device Groups', ifc=self.ifc)
                table = b.wait('list_table', frame='/contentframe')
                links = set([(x, x.text) for x in table.find_elements_by_xpath('tbody//a')])

                not_synced_dgs = [x for x in links if x[1] not in checked_dgs]
                if not not_synced_dgs:
                    break

                dg = not_synced_dgs.pop()
                checked_dgs.add(dg[1])
                dg[0].click().wait('update')
                browse_to_tab('ConfigSync', ifc=self.ifc)
                button = b.wait('export', frame='/contentframe')
                td = b.find_element_by_xpath("//table[@id='properties_table']/tbody/tr/td[2]")
                status = td.text.strip()
                LOG.debug("%s: %s", dg[1], status)
                if status != 'In Sync' and button.is_enabled():
                    button.click()
                    alert = b.switch_to_alert()
                    alert.accept()
                    LOG.info('Syncing %s...', dg[1])
                    wait_for_loading(ifc=self.ifc)
                    success &= not wait_for_task(timeout=600, ifc=self.ifc)
        else:
            # XXX: Doesn't work for Sync-only DGs.
            checked_dgs = set([])
            while True:
                browse_to('Device Management | Overview', ifc=self.ifc)
                table = b.wait('groupsTableBody', frame='/contentframe')
                rows_count = len(table.find_elements_by_xpath("tr/td[2]/img[@title!='In Sync']"))

                if rows_count == 0:
                    break

                row = table.find_element_by_xpath("tr[td[2]/img[@title!='In Sync']]")
                dg = row.get_attribute('objectname')

                if dg in checked_dgs:
                    raise RuntimeError('Trying to sync a group that was already sync-ed.')

                row.click().wait("//*[@id='groupsTableBody']/tr[@objectname='%s' and contains(@class, 'selected')]" % dg,
                                 by=By.XPATH)
                sync_button = b.wait('form_syncButton')
                sync_button.click()
                alert = b.switch_to_alert()
                alert.accept()
                LOG.info('Syncing %s...', dg)
                success &= not wait_for_task(timeout=600, ifc=self.ifc)
                checked_dgs.add(dg)

        return success
