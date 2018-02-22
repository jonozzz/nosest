'''
Created on Feb 5, 2016

@author: langer
'''
import logging

from f5test.commands.rest.base import IcontrolRestCommand

LOG = logging.getLogger(__name__)

filter_search_for_item = None
class FilterSearchForItem(IcontrolRestCommand):
    """
    Searches a URI using its built-in filter functionality for items that match
    the filter criteria.
    @return: single item AttrDict or list of items [AttrDict] from response
    """
    template = "{base_uri}?$filter={search_key}%20eq%20'{search_value}'"

    def __init__(self, base_uri, search_key, search_value, return_top_result=True, expand=True, *args, **kwargs):
        super(FilterSearchForItem, self).__init__(*args, **kwargs)
        self.base_uri = base_uri
        self.search_key = search_key
        self.search_value = search_value
        self.return_top_result = return_top_result
        self.expand = expand

    def setup(self):
        uri = self.template.format(base_uri=self.base_uri, search_key=self.search_key, search_value=self.search_value)
        LOG.info("Searching {0} for key {1} with value {2}".format(self.base_uri, self.search_key, self.search_value))
        if self.expand:
            uri += '&expandAllWithKeys=true'
        resp = self.api.get(uri)
        items = resp.get('items')
        if items and self.return_top_result:
            return items[0]
        else:
            return items

simple_rest_request = None
class SimpleRestRequest(IcontrolRestCommand):
    """
    Performs a simple REST request. This lets us provide a rest interface outside of a test class.
    @return: AttrDict of the response
    """
    def __init__(self, uri, body=None, request_type='GET', *args, **kwargs):
        super(SimpleRestRequest, self).__init__(*args, **kwargs)
        self.uri = uri
        self.body = body
        self.request_types = {'GET': self.api.get,
                              'POST': self.api.post,
                              'PATCH': self.api.patch,
                              'PUT': self.api.put,
                              'DELETE': self.api.delete}
        if request_type not in self.request_types:
            raise ValueError('HTTP request method! {0}'.format(request_type))
        self.request_type = request_type

    def run(self):
        resp = self.request_types[self.request_type](self.uri)
        return resp
