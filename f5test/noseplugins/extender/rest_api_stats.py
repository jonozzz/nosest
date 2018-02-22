'''
Created on Nov 11, 2015

@author: dodrill
'''

import logging
from . import ExtendedPlugin, PLUGIN_NAME
from ...interfaces.testcase import ContextHelper
from ...interfaces.config import ConfigInterface
from ...interfaces.rest.driver import timing_info, DELETE_STR, GET_STR,\
    PATCH_STR, POST_STR, PUT_STR
LOG = logging.getLogger(__name__)


class RestAPIStats(ExtendedPlugin):
    """
    Report on all REST API call times.
    These can be enabled/disabled by editing rest_api_stats.yaml.
    """
    enabled = False
    score = 470  # Right after Email executes
    name = "rest_api_stats"
    timing_info = []
    config = {}

    def configure(self, options, noseconfig):
        """ Do the basic configuration of this NOSE Plug-In.
        """
        super(RestAPIStats, self).configure(options, noseconfig)
        self.cfgifc = ConfigInterface()
        self.context = ContextHelper(__name__)
        self.data = ContextHelper().set_container(PLUGIN_NAME)

        # Check to see if REST API stats generation is desired
        self.config = self.cfgifc.config.get('plugins', {})
        if self.name in self.config:
            self.enabled = self.config[self.name]['enabled']

        # Only for testing
        # self.finalize(self.enabled)

    def report(self):
        """ Report the saved timing information to the log file, if that
            feature is enabled.
        """
        if self.enabled:
            LOG.info("REST API timing info:")

            def minvalue(elements):
                """ Determine the minimum timing value from the given list of
                    values. Input list is in seconds.

                    @param elements: List of timing values.
                    @return: The minimum value from the given list, in
                    milliseconds.
                """
                # Just some value that the first saved value will be less than
                minvalue = 900000000
                for element in elements:
                    if element < minvalue:
                        minvalue = element
                return minvalue * 100.0

            def maxvalue(elements):
                """ Determine the maximum timing value from the given list of
                    values. Input list is in seconds.

                    @param elements: List of timing values.
                    @return: The maximum value from the given list, in
                    milliseconds.
                """
                # Just some value that the first saved value will be greater than
                maxvalue = -900000000
                for element in elements:
                    if element > maxvalue:
                        maxvalue = element
                return maxvalue * 100.0

            def avgvalue(elements):
                """ Determine the average timing value from the given list of
                    values. Input list is in seconds.

                    @param elements: List of timing values.
                    @return: The average value from the given list, in
                    milliseconds.
                """
                total = 0
                for element in elements:
                    total += element
                return (total / len(elements)) * 100.0

            def output(method):
                """ Output the summary timing information for the given HTTP
                    method to the log file, using the data from timing_info.

                    @param method: The HTTP method to report on.
                """
                if len(timing_info[method]) == 0:
                    LOG.info(" " + method + ": No data")
                else:
                    LOG.info(" " + method +
                             ": count=%d, min=%0.fms, max=%0.fms, avg=%0.fms",
                             len(timing_info[method]),
                             minvalue(timing_info[method]),
                             maxvalue(timing_info[method]),
                             avgvalue(timing_info[method]))

            # Output all the information to the log file for each HTTP method
            output(GET_STR)
            output(PUT_STR)
            output(POST_STR)
            output(PATCH_STR)
            output(DELETE_STR)

    def finalize(self, result):
        """ If enabled, run the REST API stats reporting processes.

        @return: None.
        """
        if self.enabled is True:
            self.report()
        return None
