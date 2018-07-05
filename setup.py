from setuptools import setup, find_packages, findall
from distutils.command.build_py import build_py

VERSION = '1.0.0'

""" This file contains information that is used by the bin/buildout process,
to setup and/or refresh a virtual environment for testing.

If you have a new package to be installed, add it to the "install-requires"
list below and it will automatically be installed.  You may need to do
additional work beyond just installing the package, in order for it to be
usable in a virtual environment.
"""
media_files = [x.replace('f5test/web/', '') for x in findall('f5test/web/media/')]

addl_args = dict(
    zip_safe=False,
    cmdclass={'build_py': build_py},
    packages=find_packages(exclude=['tests', 'tests.*']),
    entry_points={
        'console_scripts': [
            'f5.install = f5test.macros.install:main',
            'f5.configurator = f5test.macros.tmosconf.placer:main',
            'f5.vcmp = f5test.macros.tmosconf.placer_vcmp:main',
            'f5.keyswap = f5test.macros.keyswap:main',
            'f5.seleniumrc = f5test.macros.seleniumrc:main',
            'f5.irack = f5test.macros.irackprofile:main',
            'f5.ha = f5test.macros.ha:main',
            'f5.ha_bigiq = f5test.macros.ha_bigiq:main',
            'f5.cloner = f5test.macros.cloner:main',
            'f5.ictester = f5test.macros.ictester:main',
            'f5.empytester = f5test.macros.empytester:main',
            'f5.trafficgen = f5test.macros.trafficgen2:main',
            'f5.webcert = f5test.macros.webcert:main',
            'f5.licensegen = f5test.macros.licensegen:main',
            'f5.loggen = f5test.macros.loggen:main',
            'f5.extractor = f5test.macros.extractor:main',
            'f5.ucs = f5test.macros.ucs_tool:main',
            'f5.testrail_importer = f5test.macros.testrail_importer:main',
            'f5.unmerge = f5test.macros.unmerge:main',
            ],
        'nose.plugins.0.10': [
            'randomize = f5test.noseplugins.randomize:Randomize',
            'config = f5test.noseplugins.testconfig:TestConfig',
            'testopia = f5test.noseplugins.testopia:Testopia',
#            'repeat = f5test.noseplugins.repeat:Repeat',
            'extender = f5test.noseplugins.extender:Extender',
            ],
        'pytest11': [
            'tcconfig = f5test.pytestplugins.config',
            'email = f5test.pytestplugins.email',
            'ite = f5test.pytestplugins.ite',
            'ansible = f5test.pytestplugins.ansible',
            'report = f5test.pytestplugins.report',
            'respool = f5test.pytestplugins.respool',
            'sidebyside = f5test.pytestplugins.side_by_side',
            'logging2 = f5test.pytestplugins.logging',
            'collector = f5test.pytestplugins.collector',
            'allure = f5test.pytestplugins.allure'
        ]
    },
)

setup(
    name='f5test',
    version=VERSION,
    author='Various',
    description='Nose System Test Framework',
    long_description='NoseST Framework - A test framework for system testing based on Nose',
    license='GNU LGPL',
    keywords='test systemtest automatic discovery',
    url='https://github.com/jonozzz/nosest',
    download_url='https://github.com/jonozzz/nosest/archive/master.zip',
    package_dir={'f5test.noseplugins.extender': 'f5test/noseplugins/extender'},
    package_data={'f5test.noseplugins.extender': ['templates/*.tmpl'],
                  'f5test.macros': ['configs/*.yaml'],
                  'f5test.web': media_files + ['views/*.tpl']},
    install_requires=[
        'paramiko',  # interfaces.ssh
        'SOAPpy',  # interfaces.icontrol
        'pyOpenSSL',  # macros.webcert
        'PyYAML',
        'pyparsing',
        'blinker',  # interfaces.config.driver
        'restkit',  # interfaces.rest.*
        'selenium',
        'jinja2',  # noseplugins.extender.email, noseplugins.extender.logcollect
        'httpagentparser',  # interfaces.selenium.core
        'dnspython',  # macros.trafficgen2
        'netaddr',
        'geventhttpclient',  # macros.trafficgen2
        'pexpect',  # interfaces.ssh.paramikospawn
        'loggerglue',  # macros.loggen, greenflash.functional.standalone.system.api.task_scheduler_basic
        'requests',  # greenflash.functional.standalone.security.migrated.scheduleDescriptions
        'influxdb',  # noseplugins.extender.grafana
        'mysql-connector-python-rf',  # noseplugins.extender.sql_reporter
        'ansible',  # Test fixtures
        'pylibmc'  # Resource pools
        'subprocess32', # Backport of py3's subprocess with timeout
        # 'pysnmp',  # interfaces.snmp.driver
        #'xmltodict',  # interfaces.rest.driver
        #'boto',
        # Openstack
        #'python-novaclient',
        #'python-glanceclient',
        #'python-neutronclient',
        # Required during by AFM's ITE libs
        #'python-dateutil',
        #'pyvmomi'
        ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Testing'
        ],
    **addl_args
    )
