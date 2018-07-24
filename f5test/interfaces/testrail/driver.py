"""Summary."""
#
# TestRail API binding for Python 2.x (API v2, available since
# TestRail 3.0)
#
# Learn more:
#
# http://docs.gurock.com/testrail-api2/start
# http://docs.gurock.com/testrail-api2/accessing
#
# Copyright Gurock Software GmbH. See license.md for details.
#

import urllib.request, urllib.error, urllib.parse
import json
import base64
from ...base import AttrDict
import logging

LOG = logging.getLogger(__name__)


class APIClient:
    """Summary.

    Attributes:
        password (str): Description
        user (str): Description
    """

    def __init__(self, base_url, debug=False):
        """Summary.

        Args:
            base_url (TYPE): Description
        """
        self.user = ''
        self.password = ''
        if not base_url.endswith('/'):
            base_url += '/'
        self.__url = base_url + 'index.php?/api/v2/'
        self.debug = debug

    #
    # Send Get
    #
    # Issues a GET request (read) against the API and returns the result
    # (as Python dict).
    #
    # Arguments:
    #
    # uri                 The API method to call including parameters
    #                     (e.g. get_case/1)
    #
    def send_get(self, uri):
        """Summary.

        Args:
            uri (TYPE): Description

        Returns:
            TYPE: Description
        """
        return self.__send_request('GET', uri, None)

    #
    # Send POST
    #
    # Issues a POST request (write) against the API and returns the result
    # (as Python dict).
    #
    # Arguments:
    #
    # uri                 The API method to call including parameters
    #                     (e.g. add_case/1)
    # data                The data to submit as part of the request (as
    #                     Python dict, strings must be UTF-8 encoded)
    #
    def send_post(self, uri, data):
        """Summary.

        Args:
            uri (TYPE): Description
            data (TYPE): Description

        Returns:
            TYPE: Description
        """
        return self.__send_request('POST', uri, data)

    def __send_request(self, method, uri, data):
        """Summary.

        Args:
            method (TYPE): Description
            uri (TYPE): Description
            data (TYPE): Description

        Returns:
            TYPE: Description

        Raises:
            APIError: Description
        """
        url = self.__url + uri
        request = urllib.request.Request(url)
        if (method == 'POST'):
            request.add_data(json.dumps(data))
        auth = base64.b64encode('%s:%s' % (self.user, self.password))
        request.add_header('Authorization', 'Basic %s' % auth)
        request.add_header('Content-Type', 'application/json')

        if self.debug:
            handler = urllib.request.HTTPHandler(debuglevel=1)
            opener = urllib.request.build_opener(handler)
            urllib.request.install_opener(opener)
        e = None
        try:
            response = urllib.request.urlopen(request).read()
        except urllib.error.HTTPError as e:
            response = e.read()

        if response:
            result = json.loads(response)
        else:
            result = {}

        if e is not None:
            if result and 'error' in result:
                error = '"' + result['error'] + '"'
            else:
                error = 'No additional error message received'
            raise APIError('TestRail API returned HTTP %s (%s)' %
                           (e.code, error))

        if isinstance(result, list):
            return [AttrDict(x) for x in result]
        return AttrDict(result)


class APIError(Exception):
    """Summary."""

    pass


class TestRail(object):
    """Class for importing test cases.

    Attributes:
        client (Instance of TestRail): client is used to perform API calls
    """

    def __init__(self, client):
        """Initializing code to None at the very beginning.

        Args:
            client (Instance of TestRail): client is used to perform API calls
        """
        self.client = client

    def get_cases(self, project_id, suite_id=None, section_id=None):
        """Return a list of testcases for a test suite/section in a test suite.

        Args:
            project_id (int): The ID of the project
            suite_id (int): The ID of the test suite (optional if the project is operating in single suite mode)
            section_id (int): The ID of the section (optional)

        Returns:
            existing_case_list (list): contains the test cases which exist
            in the selected Project, Suite and Section.
            value: Title of the test case from TestRail (filename)
        """
        path = "get_cases/" + str(project_id)
        if suite_id:
            path += "&suite_id=" + str(suite_id)
        if section_id:
            path += "&section_id=" + str()
#         existing_cases = self.client.send_get(path)
# 
#         existing_case_list = []
# 
#         for case in existing_cases:
#             title = case['title']
#             existing_case_list.append(title.encode('ascii', 'ignore'))

        return self.client.send_get(path)

    def get_projects(self):
        """Return the list of available projects.

        Returns:
            result (dict): Returns the list of available projects.
        """
        result = self.client.send_get('get_projects')
        return result

    def get_plan(self, plan_id):
        """Returns an existing test plan.
        http://docs.gurock.com/testrail-api2/reference-plans#get_plan

        Args:
            project_id (int): The ID of the test plan

        Returns:
            result (dict): Returns the test plan.
        """
        result = self.client.send_get('get_plan/' + str(plan_id))
        return result

    def get_plans(self, project_id):
        """Return the list of available plans.

        Args:
            project_id (int): The ID of the project

        Returns:
            result (dict): Returns the list of available projects.
        """
        result = self.client.send_get('get_plans/' + str(project_id))
        return result

    def get_sections(self, project_id, suite_id):
        """Return a list of sections for a project and test suite.

        Args:
            project_id (int): The ID of the project
            suite_id (int): The ID of the test suite

        Returns:
            result (dict): Returns the list of available sections in
                           the given project and suite.
        """
        result = self.client.send_get(
            'get_sections/' + str(project_id) + '&suite_id=' + str(suite_id))
        return result

    def get_suites(self, project_id):
        """Returns a list of test suites for a project.

        Args:
            project_id (int): The ID of the project

        Returns:
            result (dict): Returns a list of available suites in
                           the given project and suite.
        """
        result = self.client.send_get(
            'get_suites/' + str(project_id))
        return result

    def get_milestones(self, project_id):
        """Return the list of milestones for a project.

        Args:
            project_id (int): The ID of the project

        Returns:
            result (dict): Returns the list of milestones for a project.
        """
        result = self.client.send_get('get_milestones/' + str(project_id))
        return result

    def add_milestone(self, project_id, params):
        """Create a new milestone.

        Args:
            project_id (int): The ID of the project the milestone should be
                              added to
            params (dict): Additional request paramete

        Returns:
            result (dict): Response for creating a new milestone.
        """
        result = self.client.send_post(
            "add_milestone/" + str(project_id), params)
        return result

    def add_plan(self, project_id, params):
        """Create a new test plan.

        Args:
            project_id (int): The ID of the project the test plan should be
                               added to
            params (dict): Additional request parameters

        Returns:
            result (dict): Response for creating a new test plan.
        """
        # POST index.php?/api/v2/add_plan/:project_id
        result = self.client.send_post(
            "add_plan/" + str(project_id), params)
        return result

    def get_run(self, run_id):
        """Return an existing test run.
        http://docs.gurock.com/testrail-api2/reference-runs#get_run

        Args:
            run_id (int): The ID of the test run

        Returns:
            result (dict): Returns an existing test run.
        """
        # GET index.php?/api/v2/get_run/:run_id
        result = self.client.send_get(
            "get_run/" + str(run_id))
        return result

    def get_runs(self, project_id):
        """Returns a list of test runs for a project. Only returns those test
        runs that are not part of a test plan
        http://docs.gurock.com/testrail-api2/reference-runs#get_runs

        Args:
            project_id (int): The ID of the project

        Returns:
            result (dict): The response includes an array of configuration
                           groups, each with a list of configurations
        """
        # GET index.php?/api/v2/get_runs/:project_id
        result = self.client.send_get('/get_runs/' + str(project_id))
        return result

    def add_run(self, project_id, params):
        """Create a new test run.

        Args:
            project_id (int): The ID of the project the test plan should be
                               added to
            params (dict): Additional request parameters

        Returns:
            result (dict): Response for creating a new test plan.
        """
        # POST index.php?/api/v2/add_run/:project_id
        result = self.client.send_post(
            "add_run/" + str(project_id), params)
        return result

    def update_case(self, case_id, params):
        """Updates an existing test case (partial updates are supported, i.e.
        you can submit and update specific fields only).

        Args:
            case_id (int): The ID of the test case
            params (dict): Additional request parameters

        Returns:
            result (dict): If successful, this method returns the updated test
            case using the same response format as get_case.
        """
        # POST index.php?/api/v2/update_case/:case_id
        result = self.client.send_post(
            "update_case/" + str(case_id), params)
        return result

    def update_run(self, run_id, params):
        """Updates an existing test run (partial updates are supported, i.e.
        you can submit and update specific fields only).

        Args:
            run_id (int): The ID of the test run
            params (dict): Additional request parameters

        Returns:
            result (dict): If successful, this method returns the updated test
            run using the same response format as get_run.
        """
        # POST index.php?/api/v2/update_run/:run_id
        result = self.client.send_post(
            "update_run/" + str(run_id), params)
        return result

    def update_plan_entry(self, plan_id, entry_id, params):
        result = self.client.send_post(
            "update_plan_entry/" + str(plan_id) + '/' + str(entry_id), params)
        return result

    def add_result_for_case(self, run_id, case_id, params):
        """Create a new test run.

        Args:
            project_id (int): The ID of the project the test plan should be
                               added to
            params (dict): Additional request parameters

        Returns:
            result (dict): Response for creating a new test plan.
        """
        # POST index.php?/api/v2/add_result_for_case/:run_id/:case_id
        result = self.client.send_post(
            "add_result_for_case/" + str(run_id) + '/' + str(case_id), params)
        return result

    def get_case(self, case_id):
        """Return an existing test case.

        Args:
            case_id (int): The ID of the test case

        Returns:
            result (dict): Returns an existing test case.
        """
        # GET index.php?/api/v2/get_case/:case_id
        result = self.client.send_get(
            "get_case/" + str(case_id))
        return result

    def add_case(self, section_id, params):
        """Create a new test case.

        Args:
            section_id (int): The ID of the section the test case should be
                              added to
            params (dict): Additional request parameters

        Returns:
            result (dict): Response for creating a new test case
        """
        result = self.client.send_post('add_case/' + str(section_id), params)
        return result

    def add_section(self, project_id, params):
        """Creates a new section.

        Args:
            project_id (int): The ID of the project
            params (dict): Additional request parameters

        Returns:
            result (dict): Response for creating a new test case
        """
        result = self.client.send_post('add_section/' + str(project_id), params)
        return result

    def add_plan_entry(self, plan_id, params):
        """Add one or more new test runs to a test plan.

        Args:
            plan_id (int): The ID of the plan the test runs should be added to
            params (dict): Additional request parameters

        Returns:
            result (dict): : Reponse content for adding a plan entry
        """
        # POST index.php?/api/v2/add_plan_entry/:plan_id
        result = self.client.send_post(
            "add_plan_entry/" + str(plan_id), params)
        return result

    def get_configs(self, project_id):
        """Return a list of available configs, grouped by config groups.

        Args:
            project_id (int): The ID of the project

        Returns:
            result (dict): The response includes an array of configuration
                           groups, each with a list of configurations
        """
        # GET index.php?/api/v2/get_configs/:project_id
        result = self.client.send_get('/get_configs/' + str(project_id))
        return result

    def add_config(self, config_group_id, params):
        """Create a new configuration.

        Args:
            config_group_id (int): The ID of the configuration group the
                                   configuration should be added to
            params (dict): Additional request parameters

        Returns:
            result (dict): Reponse content for adding new configuration
        """
        result = self.client.send_post(
            '/add_config/' + str(config_group_id), params)
        return result

    def get_tests(self, run_id):
        """Return existing tests from a run_id.

        Args:
            run_id (int): The ID of the test run

        Returns:
            result (dict): Reponse content with existing tests in a run_id
        """
        # GET index.php?/api/v2/get_tests/:run_id
        result = self.client.send_get("get_tests/" + str(run_id))
        return result

    def add_result(self, test_id, params):
        """Add a new test result, comment or assigns a test.

        Args:
            test_id (int): The ID of the test the result should be added to
            params (dict): Additional request parameters

        Returns:
            result (dict): Response content for adding a new result
        """
        # POST index.php?/api/v2/add_result/:test_id
        result = self.client.send_post("add_result/" + str(test_id), params)
        return result
