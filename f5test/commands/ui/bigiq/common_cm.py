'''
Created on Dec 9, 2015

Methods are specific to BIG-IQ CM >= 5.0

@author:
'''

from ..base import SeleniumCommand
from ....interfaces.config import ConfigInterface, DeviceAccess
from ....interfaces.selenium import By, Is
import logging
import time
from f5test.utils.wait import wait, WaitTimedOut
from selenium.common.exceptions import (NoSuchElementException,
                                        StaleElementReferenceException,
                                        ElementNotVisibleException)
from f5test.commands.ui.uiutils import (webel_grab, webel_click, input_send,
                                        wait_for_text_in_webel as wait_ftw,
                                        wait_for_webel)
from f5test.interfaces.selenium import ActionChains

LOG = logging.getLogger(__name__)


class WrongParameterPassedMethodCheck(Exception):
    """Error to be raised in case Parameters are not passed properly..."""
    pass


class WrongMethodForVersionCheck(Exception):
    """Error to be raised in case version does not support method..."""
    pass

login = None
class Login(SeleniumCommand):  # @IgnorePep8
    """Log in command.

    @param device: The device.
    @type device: str or DeviceAccess instance
    @param address: The IP or hostname.
    @type address: str
    @param username: The username.
    @type username: str
    @param password: The password.
    @type password: str
    """
    def __init__(self, device=None, address=None, username=None, password=None,
                 port=None, proto='https', timeout=15, ver=None, *args, **kwargs):
        super(Login, self).__init__(*args, **kwargs)
        self.timeout = timeout
        self.proto = proto
        self.path = '/ui/login/'
        if device or not address:
            self.device = device if isinstance(device, DeviceAccess) else ConfigInterface().get_device(device)
            self.address = address or self.device.address
            self.port = port or self.device.ports.get(proto, 443)
            self.username = username or self.device.get_admin_creds().username
            self.password = password or self.device.get_admin_creds().password
        else:
            self.device = device
            self.address = address
            self.port = port
            self.username = username
            self.password = password
        self.ver = ver

    def setup(self):
        b = self.api

        # Set the api login data
        self.ifc.set_credentials(device=self.device, address=self.address,
                                 username=self.username, password=self.password,
                                 port=self.port, proto=self.proto)
        if not self.ver:
            self.ver = self.ifc.version
        LOG.info("Login with [{0}]...".format(self.username))

        url = "{0[proto]}://{0[address]}:{0[port]}{0[path]}".format(self.__dict__)
        b.get(url)
        # The login page might be outdated (from an old version)
        b.refresh().wait('username', timeout=self.timeout)

        e = b.find_element_by_name("username")
        e.click()
        e.send_keys(self.username)

        e = b.find_element_by_id("passwd")
        e.send_keys(self.password)
        if self.ver >= 'bigiq 4.1' or \
                self.ver < 'bigiq 4.0':  # This is BIG-IQ OR
            e.submit().wait('navMenu', timeout=self.timeout)
        elif self.ifc.version < 'bigiq 4.1':
            e.submit().wait('loginDiv', timeout=self.timeout)

        b.maximize_window()


navigate = None
class Navigate(SeleniumCommand):  # @IgnorePep8
    """Navigate to another BIGIQ module.

    @param module: The navMenu path
                    (e.g. Device Management, Device Management|Operations)
    @type module: str
    @return: The navLink element
    """
    def __init__(self, module=None, timeout=15, *args, **kwargs):
        super(Navigate, self).__init__(*args, **kwargs)
        self.module = module
        self.timeout = timeout
        self.ver = self.ifc.version

    def setup(self):
        b = self.api
        LOG.info("Navigate to [{0}]...".format(self.module))
        bits = self.module.split('|')

        current_menu_xpath = '//div[@id="navMenuCurrentLink"]'
        link_xpath = '//div[@id="navMenu"]/ul//li/a[text()="%s"]' % (bits[0])

        # Click on Product if not already there
        current_menu = webel_grab(xpath=current_menu_xpath, use_js=False, ifc=self.ifc)
        if current_menu and bits[0] not in current_menu[0]["text"]:
            webel_click(xpath=link_xpath, jsclick=True, ifc=self.ifc)
            wait_ftw(xpath=current_menu_xpath, text=bits[0], ifc=self.ifc)
            time.sleep(2)  # workaround BZ
        if len(bits) > 1:
            tail = "//a[text()='%s']" % bits[1]
            link_xpath = "//div[@id='navMenuSublinks']%s" % (tail)
            webel_click(xpath=link_xpath, jsclick=True, ifc=self.ifc)
            wait_ftw(xpath=link_xpath, text=bits[1], ifc=self.ifc)
            time.sleep(2)  # workaround BZ
            if len(bits) == 3:
                tail = '//div[a[text()="{0}"]][div[a[text()="{1}"]]]//a[text()="{1}"]'.format(bits[1], bits[2])
                link_xpath = "//div[@id='navMenuSublinks']%s" % (tail)
                webel_click(xpath=link_xpath, jsclick=True, ifc=self.ifc)
                wait_ftw(xpath=link_xpath, text=bits[2], ifc=self.ifc)
                time.sleep(2)  # workaround BZ
        wait_ftw(xpath=current_menu_xpath, text=bits[0], ifc=self.ifc)

        # Do not wait for the link to be active yet as it's not working, sleep instead
        # b = b.wait(wait_xpath, By.XPATH, timeout=self.timeout)

#         waitforspinners = True
#         waitforspinners_x = '//*[contains(concat(normalize-space(@class), " "),"spinner ") and not(contains(concat(" ", @class, " "), " cell-spinner ")) and not(contains(concat(" ", @class, " "), " security-spinner ")) and not(contains(concat(" ", @class, " "), " loading-spinner "))]'
#         spinners = webel_grab(xpath=waitforspinners_x, ifc=self.ifc)
#         if len(spinners) == 0:
#             waitforspinners = False
#         if waitforspinners:
#             wait_ftw(text='ng-hide',
#                      xpath=waitforspinners_x,
#                      textineach=True,
#                      attr=['class'],  # prop=["is_displayed"],
#                      ifc=self.ifc, timeout=60 if self.timeout < 60 else self.timeout,
#                      usedin='Navigate[{0}]/WaitForSpinners'.format(self.module))

        return b


logout = None
class Logout(SeleniumCommand):  # @IgnorePep8
    """Log out from UI. Requires that someone is logged in already.

    @param timeout: default timeout to wait for this action.
    @type timeout: int
    @param jclick: default True: Use a javascript click (for not displayed els)
    @type jclick: bool
    """
    def __init__(self, timeout=20, jclick=True, *args, **kwargs):
        super(Logout, self).__init__(*args, **kwargs)
        self.timeout = timeout
        self.jclick = jclick
        # self.user_d = "userName"
        self.logout_link_d = "logOutLink"
        self.logo_d = "logo"

    def setup(self):
        LOG.info("Logging out of UI...")
        s = self.api

        # also accounting for some weird refresh while performing this:
        def do_log_out():
            bee = True
            # Is it already logged out?
            try:
                s.find_element_by_id(self.logo_d)
            except (ElementNotVisibleException, NoSuchElementException):
                bee = False
                try:
                    # s.wait(self.user_d)
                    # current_user = s.find_element_by_id(self.user_d)
                    # ActionChains(s).move_to_element(current_user).perform()
                    # s.wait(self.logout_link_d)
                    btn = s.find_element_by_id(self.logout_link_d)
                    # sometimes element is found before it can be clicked.
                    time.sleep(1)
                    if not self.jclick:
                        btn.click()
                    else:
                        s.execute_script("return arguments[0].click()", btn)
                except (ElementNotVisibleException, NoSuchElementException):
                    bee = False
            return bee
        wait(do_log_out, interval=1, timeout=self.timeout)
        return s.wait(self.logo_d, timeout=self.timeout)

left_menu_toggle = None
class LeftMenuToggle(SeleniumCommand):  # @IgnorePep8
    """Toggle left menu to be expanded or retracted - object browser

    Optional parameters:
    @param expand: True by default
    @type expand: bool

    @return: bool
    """
    def __init__(self, expand=True,
                 *args, **kwargs):
        super(LeftMenuToggle, self).__init__(*args, **kwargs)

        self.expand = expand

    def setup(self):
        toggle_x = '//object-browser/object-browser-nav/div[not(contains(concat(" ", @class, " "), " ng-hide "))]/div[@class="navToggle"]/a'
        arrow_x = '//object-browser/object-browser-nav/div[not(contains(concat(" ", @class, " "), " ng-hide "))]/div[@class="navToggle"]/a/sprite[contains(concat(" ", normalize-space(@class), " ")," sprite")]'
        menu_expanded = False
        arrow_class = webel_grab(xpath=arrow_x, attr=["class"], ifc=self.ifc)[0]["class"]
        if "arrow_collapse_left" in arrow_class and "arrow_expand_right" not in arrow_class:
            menu_expanded = True
        if self.expand and not menu_expanded:
            webel_click(xpath=toggle_x,
                        waitfortext="arrow_collapse_left",
                        inxpath=arrow_x,
                        attr=["class"],
                        ifc=self.ifc)
            LOG.info("/UI/Found Collapsed Menu and Did Expand.")
        elif not self.expand and menu_expanded:
            webel_click(xpath=toggle_x,
                        waitfortext="arrow_expand_right",
                        inxpath=arrow_x,
                        attr=["class"],
                        ifc=self.ifc)
            LOG.info("/UI/Found Expanded Menu and Did Collapse.")
        return True

object_nav = None
class ObjectNav(SeleniumCommand):  # @IgnorePep8
    """Object Navigate through the left menu - object browser only

    @param navtree: example: BIG-IQ DEVICES|BIG-IQ HA
    @type navtree: str

    Optional parameters:
    @param expand: True by default (navigate with the left menu expanded or collapsed?)
    @type expand: bool
    @param collapse_last: Collapse (back) last requested object (that can be collapsed).
                          False by default.
    @type collapse_last: bool

    @return: bool
    """
    def __init__(self, navtree,
                 expand=True, collapse_last=False,
                 *args, **kwargs):
        super(ObjectNav, self).__init__(*args, **kwargs)

        self.navtree = navtree
        self.expand = expand
        self.collapse_last = collapse_last

    def setup(self):
        LOG.info("/UI/To Menu [{1}][{0}]{2}...".format(self.navtree,
                                                       "expanded" if self.expand else "collapsed",
                                                       "[collapse tree]" if self.collapse_last else ""))
        bits = self.navtree.split('|')
        left_menu_toggle(expand=self.expand, ifc=self.ifc)
        if self.expand:
            menu_item_x = '//object-browser/object-browser-nav/div[contains(concat(" ", normalize-space(@class), " ")," expandedNav ")]'
            menu_link_x = None
            menu_item_span_x = None
            arrow_class = None
            expanded_down = False
            for bit in bits:
                menu_item_x = '{0}/ul/li[a[contains(., "{1}") and not(contains(concat(" ", @class, " "), " ng-hide "))]]'.format(menu_item_x, bit)
                menu_link_x = '{0}/a[contains(., "{1}") and not(contains(concat(" ", @class, " "), " ng-hide "))]'.format(menu_item_x, bit)
                menu_item_span_x = '{0}/span'.format(menu_link_x)
                arrow = webel_grab(xpath=menu_item_span_x, attr=["class"], ifc=self.ifc)
                arrow_class = None
                if arrow:
                    arrow_class = arrow[0]["class"]
                expanded_down = False
                if arrow_class and "caret_right" not in arrow_class and "caret_down" in arrow_class:
                    expanded_down = True
                a_class = webel_grab(xpath=menu_item_x, attr=["class"], ifc=self.ifc)
                selected = False
                if a_class and "selected" in a_class[0]["class"]:
                    selected = True
                if not selected:
                    if arrow_class:
                        if not expanded_down:
                            webel_click(xpath=menu_link_x,
                                        waitfortext="caret_down",
                                        inxpath=menu_item_span_x,
                                        attr=["class"],
                                        ifc=self.ifc)
                    else:
                        webel_click(xpath=menu_link_x,
                                    waitfortext="selected",
                                    inxpath=menu_link_x,
                                    attr=["class"],
                                    ifc=self.ifc)
            if self.collapse_last and arrow_class and menu_link_x and menu_item_span_x and expanded_down:  # reuse last expandable menu
                webel_click(xpath=menu_link_x,
                            waitfortext="caret_right",
                            inxpath=menu_item_span_x,
                            attr=["class"],
                            ifc=self.ifc)
        else:
            LOG.error("Navigate with collapsed menu - not implemented yet.")
        LOG.info("/UI/On Menu. Sleep 1s.")
        time.sleep(1)  # give some time to stabilize - no good way of knowing what the yielded page is
        return True
