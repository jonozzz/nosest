'''
Created on Mar 29, 2018

Depends on pytest-json-report

@author: jono
'''


def mark_to_str(marker):
    if marker.args:
        if len(marker.args) == 1:
            return {marker.name: marker.args[0]}
        else:
            return {marker.name: marker.args}
    else:
        return {marker.name: True}


def get_markers(item):
    for keyword in item.keywords.keys():
        if not any((keyword == 'parametrize',)):
            marker = item.get_marker(keyword)
            if marker:
                yield mark_to_str(marker)


def pytest_json_modifytest(item, call, test):
    if call.when == 'setup':
        test['markers'] = list(get_markers(item))
