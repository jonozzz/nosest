'''
Created on Mar 8, 2013

@author: jono
'''
import os
from f5test.utils.cm import create_finder, IsoNotFoundError, version_from_metadata
from f5test.utils.version import Product, Version
import re


def sanitize_atom_path(path):
    # ATOM sometimes passes ISOs that are not available in Seattle
    # Example: /build/bigip/project/tmos-bugs/daily/build755.200/BIGIP-tmos-bugs-12.0.0.0.0.755.iso
    # Convert it to: /build/bigip/project/tmos-bugs/daily/build755.0/BIGIP-tmos-bugs-12.0.0.0.0.755.iso
    SEATTLE_SUFFIX = '0'
    if not path:
        return path
    return re.sub(r'/build(\d+)\.\d+/', r'/build\1.%s/' % SEATTLE_SUFFIX, path)


def file_validator(value, **kwargs):
    return value and os.path.exists(value) or 'File not found'


def split_hf(project):
    m = re.match('([\d\.]+)-(hf[\-\w]+)', project or '')
    if m:
        return m.groups()
    return (project, None)


def project_validator(value, product=Product.BIGIP, **kwargs):
    if value:
        try:
            project, hotfix = split_hf(value)
            create_finder(project, hotfix=hotfix, product=product).find_file()
            return True
        except IsoNotFoundError:
            return 'Invalid project'


def build_validator(value, project=None, hotfix=None, product=Product.BIGIP, **kwargs):
    if hotfix and 'eng' == hotfix.lower() and not value:
        return 'Invalid ENG hotfix build'
    if value and project:
        try:
            project2, hotfix2 = split_hf(project)
            create_finder(identifier=project2, build=value,
                          hotfix=hotfix or hotfix2, product=product).find_file()
            return True
        except IsoNotFoundError:
            if hotfix:
                return 'Invalid build for {0} hotfix {1}'.format(project, hotfix)
            return 'Invalid build for %s' % project


def hotfix_validator(value, project=None, build=None, product=Product.BIGIP, **kwargs):
    if value and project:
        if 'eng' == value.lower():
            return True
        try:
            create_finder(identifier=project, build=build or None, hotfix=value,
                          product=product).find_file()
            return True
        except ValueError as e:
            return str(e)
        except IsoNotFoundError:
            return 'Invalid hotfix for %s' % project


def min_version_validator(value=None, project=None, hotfix=None, product=Product.BIGIP,
                          iso=None, min_ver='bigip 11.4.0', **kwargs):
    if hotfix and 'eng' == str(hotfix).lower() and not value:
        return 'Invalid ENG hotfix build'
    if iso:
        isofile = sanitize_atom_path(iso)
    elif value and project:
        try:
            project2, hotfix2 = split_hf(project)
            isofile = create_finder(identifier=project2, build=value,
                                    hotfix=hotfix or hotfix2, product=product).find_file()
        except IsoNotFoundError:
            if hotfix:
                return 'Invalid build for {0} hotfix {1}'.format(project, hotfix)
            return 'Invalid build for %s' % project
    else:
        raise NotImplementedError('Need build and project or iso')
    iso_version = version_from_metadata(isofile)
    return iso_version >= Version(min_ver)


def max_version_validator(value=None, project=None, hotfix=None,
                          product=Product.BIGIP,
                          iso=None, max_ver='bigip 14', **kwargs):
    """ Make sure that we aren't trying to run tests on a BIG-IP version that
        is too new to be supported.
    """
    if hotfix and 'eng' == str(hotfix).lower() and not value:
        return 'Invalid ENG hotfix build'
    if iso:
        isofile = sanitize_atom_path(iso)
    elif value and project:
        try:
            project2, hotfix2 = split_hf(project)
            isofile = create_finder(identifier=project2, build=value,
                                    hotfix=hotfix or hotfix2,
                                    product=product).find_file()
        except IsoNotFoundError:
            if hotfix:
                return 'Invalid build for {0} hotfix {1}'.format(project, hotfix)
            return 'Invalid build for %s' % project
    else:
        raise NotImplementedError('Need build and project or iso')
    iso_version = version_from_metadata(isofile)
    return iso_version < Version(max_ver)


validators = {'file': file_validator,
              'project': project_validator,
              'build': build_validator,
              'hotfix': hotfix_validator,
}
