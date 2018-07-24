
from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.command import Command
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys  # @UnusedImport
from selenium.common.exceptions import (NoSuchElementException,
                                        StaleElementReferenceException, NoSuchWindowException)

from ...utils.wait import Wait, wait
from ...base import Options
import copy
import time
import logging
import uuid

LOG = logging.getLogger(__name__)


class ConditionError(Exception):
    pass


class Is(object):
    DISPLAYED = "is_displayed"
    VISIBLE = "is_displayed"  # alias of DISPLAYED
    SELECTED = "is_selected"
    ENABLED = "is_enabled"
    PRESENT = 0
    TEXT_MATCH = 1
    CUSTOM_MATCH = 2


class NONEGIVEN:
    pass


class ElementWait(Wait):

    def __init__(self, element, *args, **kwargs):
        self._frame = None
        self._it = None
        self._match = None
        self._element = element
        return super(ElementWait, self).__init__(*args, **kwargs)

    def function(self, value=None, by=By.ID, frame=None, it=Is.DISPLAYED, match=None):
        if not self._frame:
            self._frame = frame
        self._it = it
        self._match = match
        # Start from an element (if specified) or the entire DOM.
        parent = self._element

        f = Options()
        f.by = by
        f.value = value
        f.stabilize = self.stabilize
        f.negated = 'yes' if self.negated else 'no'
        f.frame = '.' if frame is None else frame

        if it == Is.VISIBLE or it == Is.DISPLAYED:
            f.state = 'visible'
        elif it == Is.SELECTED:
            f.state = 'selected'
        elif it == Is.ENABLED:
            f.state = 'enabled'
        elif it == Is.TEXT_MATCH:
            f.state = 'text_match'
        elif it == Is.CUSTOM_MATCH:
            f.state = 'custom_match'
        else:
            f.state = 'present'

        self._criteria = "by={0.by} value={0.value} frame={0.frame} " \
                         "state={0.state} negated={0.negated} " \
                         "stabilize={0.stabilize}".format(f)
        self.timeout_message = "Criteria: {0} not met after {{0}} seconds.".format(self._criteria)
        LOG.debug("Waiting for: {0}".format(self._criteria))

        b = parent.parent if isinstance(parent, WebElement) else parent
        assert isinstance(b, RemoteWebDriver)

        # XXX: Workaround for a Selenium + FF14.0 (and above) issue, where the
        # current frame is lost in certain situations and the context is
        # switched to the default document. For more see:
        # http://code.google.com/p/selenium/issues/detail?id=4309
        #
#        if self._frame:
        frame = f.frame
        b.switch_to_frame(frame, forced=True)
        # Absolutize the frame (in case the one provided was relative)
        self._frame = b.get_current_frame()

        if not value:
            self._result = self._element
            return
        self._result = parent.find_element(by=by, value=value)

    def test_result(self):
        ret = None
        if self._it == Is.PRESENT:
            ret = True
        elif self._it == Is.TEXT_MATCH:
            ret = self._match in self._result.text
        elif self._it == Is.CUSTOM_MATCH:
            assert callable(self._match), 'match argument must be a function'
            ret = self._match(self._result)
        else:
            ret = getattr(self._result, self._it)()

        return bool(ret) ^ self.negated

    def test_error(self, exc_type, exc_value, exc_traceback):
        if exc_type is NoSuchElementException:
            if (self._it in (Is.PRESENT, Is.DISPLAYED) and self.negated):
                return True
        elif exc_type in (IndexError, StaleElementReferenceException):
            LOG.debug(exc_value)

        return False


class WebElementWrapper(WebElement):
    def __repr__(self):
        return "<WebElement %s>" % self.id

    def wait(self, *args, **kwargs):
        """Waits for condition c"""
        return self.parent.wait(*args, element=self, **kwargs)

    def click(self, *args, **kwargs):
        """condition wrapped"""
        super(WebElementWrapper, self).click(*args, **kwargs)
        return self.parent

    def jquery_click(self, *args, **kwargs):
        """A click() method that works on invisible elements without hovering.
        jQuery lib is required!"""
        self.parent.execute_script("return arguments[0].click()", self)
        return self.parent

    def jsclick(self, *args, **kwargs):
        """same as jquery_click"""
        self.parent.execute_script("return arguments[0].click()", self)
        return self.parent

    def double_click(self, *args, **kwargs):
        ActionChains(self.parent).double_click(self).perform()
        return self.parent

    def show(self, style='inline'):
        self.parent.execute_script("return arguments[0].style.display='%s'" % style, self)
        return self.parent

    def submit(self, *args, **kwargs):
        """condition wrapped"""
        super(WebElementWrapper, self).submit(*args, **kwargs)
        return self.parent

    def hover(self):
        """Gets the location."""
        self.parent.execute(Command.MOVE_TO, {'element': self.id})
        return self.parent

    def find_element(self, by=By.ID, value=None):
        # Reason for this is that if you do:
        #   parent.find_element_by_xpath('//span')
        # will return all <span>'s in the entire page not from parent.
        #
        # If you look at xpath syntax for '//' it clearly says:
        # "Selects nodes in the document from the current node that match the
        # selection no matter where they are"
        if by == By.XPATH and value.startswith('/'):
            value = '.' + value
        return super(WebElementWrapper, self).find_element(by=by, value=value)


class RemoteWrapper(RemoteWebDriver):

    def __init__(self, *args, **kwargs):
        self._frames = {}
        self._current_window_handle = None
        return super(RemoteWrapper, self).__init__(*args, **kwargs)

    @property
    def current_window_handle(self):
        """
        Cache and return the handle of the current window.

        :Usage:
            driver.current_window_handle
        """
        if not self._current_window_handle:
            self._current_window_handle = super(RemoteWrapper, self).current_window_handle
        return self._current_window_handle

    def switch_to_frame(self, frame_path='.', window_handle=None, forced=False):
        """Switches focus to a frame by index or name.

        @param frame_path: The frame path (e.g. /frame1/subframe or ../parent)
        @param window: The window handle
        @param forced: Attempt to switch frames even we're out of sync
        """
        if window_handle is None:
            window_handle = self.current_window_handle
        orig_frames = self._frames.setdefault(window_handle, [])
        frames = copy.copy(orig_frames)

        for i, bit in enumerate(frame_path.split('/')):
            if bit == '':
                # Path starts with a / (absolute)
                if i == 0:
                    frames[:] = []
                # Path ends / (ignore it)
                else:
                    continue
            elif bit == '..':
                try:
                    # Go up one level
                    frames.pop()
                except IndexError:
                    # We've reached the bottom already
                    continue
            elif bit == '.':
                # Ignore it
                continue
            else:
                frames.append(bit)

        if forced or frames != orig_frames:
            try:
                super(RemoteWrapper, self).switch_to.default_content()
                for frame in frames:
                    super(RemoteWrapper, self).switch_to.frame(frame)
                orig_frames[:] = frames
            except:
                # Attempt to revert the positioning in the frames chain
                super(RemoteWrapper, self).switch_to.default_content()
                for frame in orig_frames:
                    super(RemoteWrapper, self).switch_to.frame(frame)
                raise

    def get_current_frame(self, window_handle=None):
        """Returns the frame locator for the given window.

        @param window: The window handle
        """
        if window_handle is None:
            window_handle = self.current_window_handle
        return '/' + '/'.join(self._frames.setdefault(window_handle, []))

    def switch_to_default_content(self):
        """Switches to the topmost frame (aka _top)."""
        return self.switch_to_frame('/')

    def switch_to_window(self, window_name, frame=None, timeout=3):
        """Switching the window automatically resets the current frame to _top.

        @param window_name: Window handle or name
        @param frame: Frame path to set inside the window. By default it'll set
        the last frame path and if none is set it'll be /.
        @param timeout: Wait this long for the window to become available.
        @type timeout: int (seconds)
        """
        interval = 0.1
        now = start = time.time()

        while True:
            try:
                super(RemoteWrapper, self).switch_to.window(window_name)
                # Kill the cached value
                self._current_window_handle = None
                break
            except NoSuchWindowException:
                LOG.debug('Window %s not yet present.', window_name)
                if now - start >= timeout:
                    raise

            time.sleep(interval)
            now = time.time()

        if frame is None:
            frame = self.get_current_frame()
        self.switch_to_frame(frame, forced=True)

    def create_web_element(self, element_id):
        """Override from RemoteWebDriver to use firefox.WebElement."""
        return WebElementWrapper(self, element_id)

    def move_to_element(self, to_element):
        """Moving the mouse to the middle of an element.
        Args:
            to_element: The element to move to.
        """
        return self.execute(Command.MOVE_TO, {'element': to_element.id})
        # return self.execute(Command.HOVER_OVER_ELEMENT, {'id': to_element.id})

    def get(self, *args, **kwargs):
        """Loads a web page in the current browser."""
        super(RemoteWrapper, self).get(*args, **kwargs)
        self.switch_to_default_content()
        return self

    def refresh(self, *args, **kwargs):
        """Refreshes the current page and return self instance to help chaining methods."""
        super(RemoteWrapper, self).refresh(*args, **kwargs)
        return self

    def open_window(self, location='', name=None, tokens=''):
        """Opens up a new tab or window."""
        if name is None:
            name = uuid.uuid4().hex
        script = "window.open('%s','%s', '%s')" % (location, name, tokens)
        super(RemoteWrapper, self).execute_script(script)
        return name

    def maximize_window(self):
        self.set_window_position(0, 0)
        self.set_window_size(1366, 768)

    def wait(self, value=None, by=By.ID, frame=None, it=Is.DISPLAYED,
             negated=False, timeout=10, interval=0.1, stabilize=0, element=None,
             match=None):
        """Waits for an element to satisfy a certain condition.

        @param value: the locator
        @type value: str
        @param by: the locator type, one of: ID, XPATH, LINK_TEXT, NAME,
                   TAG_NAME, CSS_SELECTOR, CLASS_NAME
        @type by: enum
        @param frame: the frame path (e.g. /topframe/subframe, default: current frame)
        @type frame: str
        @param it: condition, one of: DISPLAYED, SELECTED, ENABLED, PRESENT
        @type it: enum
        @param negated: negate the condition if true
        @type negated: bool
        @param timeout: timeout (default: 10 sec)
        @type timeout: int
        @param interval: polling interval
        @type interval: int
        @param stabilize: how long to wait after the condition is satisfied to
                          make sure it doesn't change again (default: 0 sec)
        @type stabilize: int
        @param element: parent element
        @type element: WebElement instance
        """

        w = ElementWait(element or self, timeout, interval, stabilize, negated)
        return w.run(value, by, frame, it, match)

    def wait_ajax(self, timeout=10, interval=0.1, stabilize=0):
        """Waits for the number of jQuery Ajax calls to drop to 0."""
        def xhr_pending():
            return self.execute_script('return $.active;') == 0

        return wait(xhr_pending, timeout=timeout, interval=interval,
                    stabilize=stabilize)

    def execute(self, driver_command, params=None):
        """
        Selenium's debug logging is really dumb and useless. Override it here.
        """
        def pretty(x):
            if x:
                return ', '.join(["%s='%s'" % (n, str(v)[:1024])
                                  for n, v in x.items() if n != 'sessionId'])
            else:
                return ''

        LOG.debug('{0}({1})'.format(driver_command, pretty(params)))
        ret = super(RemoteWrapper, self).execute(driver_command, params)
        LOG.debug('{0}'.format(pretty(ret)))
        return ret
