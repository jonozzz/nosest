'''
Created on Mar 29, 2018

@author: jono
'''


def mark_to_str(marker):
    if marker.args:
        return {marker.name: marker.args[0]}
    else:
        return {marker.name: True}


def get_markers(item):
    for keyword in item.keywords.keys():
        if not any((keyword == 'parametrize',)):
            marker = item.get_marker(keyword)
            if marker:
                yield mark_to_str(marker)


def pytest_runtest_call(item):
    markers = list(get_markers(item))
    if hasattr(item.config, '_json'):
        item.config._json.nodes[item.nodeid]['markers'] = markers
