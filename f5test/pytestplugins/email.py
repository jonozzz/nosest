'''
Created on Mar 29, 2018

Depends on pytest-json-report

@author: jono
'''
from __future__ import absolute_import

import copy
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os
import re
import smtplib
import pytest

import jinja2

from ..interfaces import ContextHelper
import f5test.commands.icontrol as ICMD
from ..base import AttrDict
from ..utils.convert import to_bool
from ..utils import Version
from ..interfaces.config import DeviceAccess
from ..utils.progress_bar import ProgressBar

LOG = logging.getLogger(__name__)
DEFAULT_FROM = 'pytest-results@f5.com'
DEFAULT_SUBJECT = 'Test Run'
MAIL_HOST = 'mail'
DUMP_EMAIL_FILENAME = 'email.html'

ROLE_NAMES = {0: 'ADMIN_ROLE', 1: 'ROOT_ROLE', 2: 'DEFAULT_ROLE'}


def encode(obj):
    """Transform some of the useful objects into JSON serializable types"""
    ret = AttrDict()
    if isinstance(obj, Version):
        ret.version = obj.version
        ret.build = obj.build
        ret.product = obj.product.to_tmos

    elif isinstance(obj, DeviceAccess):
        ret.address = obj.address
        ret.alias = obj.alias
        ret.ports = obj.ports
        ret.credentials = AttrDict()
        for role, level_cred in obj.credentials.items():
            role = ROLE_NAMES[role]
            ret.credentials[role] = AttrDict()
            for level, cred in level_cred.items():
                ret.credentials[role][level] = AttrDict(username=cred.username,
                                                        password=cred.password)
        ret.is_default = obj.is_default()
        ret.hostname = obj.hostname
        ret.discovery_address = obj.get_discover_address()

    return ret


def pytest_configure(config):
    config.pluginmanager.register(EmailPlugin(config), 'email-plugin')


def customfilter_ljust(string, width, fillchar=' '):
    if string is None or isinstance(string, jinja2.Undefined):
        return string

    return string.ljust(width, fillchar)


def customfilter_rjust(string, width, fillchar=' '):
    if string is None or isinstance(string, jinja2.Undefined):
        return string

    return string.rjust(width, fillchar)


def customfilter_bzify(string):
    if string is None or isinstance(string, jinja2.Undefined):
        return string

    links = {'((?:BZ|BUG)\s*(\d{6}))':
             r"<a href='http://bugzilla/show_bug.cgi?id=\2'>\1</a>"}
    result = string
    for expr, href in links.items():
        result = re.sub(expr, href, result, flags=re.IGNORECASE)
    return result if result == string else jinja2.filters.do_mark_safe(result)


def customfilter_product(duts, product='bigip'):
    if duts is None or isinstance(duts, jinja2.Undefined) or\
            not isinstance(duts, list) or not isinstance(product, basestring):
        return duts

    result = list()
    for dut in duts:
        if dut.version.product.product == product:
            result.append(dut)

    return result


class EmailPlugin(object):
    """
    Send email report.
    """
    def __init__(self, config):
        self.config = config
        if hasattr(config, '_tc'):
            self.options = config._tc.plugins.email or AttrDict()
            self.enabled = to_bool(self.options.enabled)
        else:
            self.enabled = False
        self.context = ContextHelper()

    def options(self, parser, env):
        """Register commandline options."""
        parser.add_option('--with-email', action='store_true',
                          dest='with_email', default=False,
                          help="Enable Email reporting. (default: no)")

    def duts_details(self):
        for device in self.context.get_config().get_devices():
            info = AttrDict()
            info.device = encode(device)
            try:
                info.platform = ICMD.system.get_platform(device=device)
                info.version = encode(ICMD.system.get_version(device=device))
                v = ICMD.system.parse_version_file(device=device)
                info.project = v.get('project')
                info.edition = v.get('edition', '')
            except Exception as e:
                LOG.error("%s: %s", type(e), e)
                info.version = encode(Version())
                info.platform = ''
            yield info

    def make_bars(self):
        assert self.data.result is not None
        self.data.result.bars = {}
        b = self.data.result.bars
        result = self.data.test_result
        passed_count = len(self.data.result.passed)
        total = result.failCount() + result.notFailCount() + passed_count
        b.good = ProgressBar(total, total - result.failCount() - result.notFailCount())
        b.bad = ProgressBar(total, result.failCount())
        b.unknown = ProgressBar(total, result.notFailCount())
        b.ki = ProgressBar(total, len(result.known_issue))

        # New progress bars for when Skipped tests should be ignored.
        b.good_no_skips = ProgressBar(total - result.notFailCount(),
                                      total - result.failCount() - result.notFailCount())
        b.bad_no_skips = ProgressBar(total - result.notFailCount(),
                                     result.failCount())

        x = {}
        for label, storage in result.blocked.items():
            for truple in storage:
                test, err, context = truple
                y = x.setdefault(label, {})
                z = y.setdefault(context, [])
                z.append((test, err))
        self.data.result.blocked_groups = x

    def compile_emails(self, data):
        base = self.options
        recipients = []
        specs = base.multi if base.multi else [base]

        for spec in specs:
            tmp = copy.copy(base)
            tmp.update(spec)
            spec = tmp
            #if self.noseconfig.options.with_email_subject:
            #    spec.subject = self.noseconfig.options.with_email_subject
            #elif self.data.config.testrun.description:
            #    spec.subject = self.data.config.testrun.description
            #else:
            spec.subject = spec.get('subject', DEFAULT_SUBJECT)
            headers = AttrDict()
            if not spec:
                LOG.warning('Email plugin not configured.')
                return
            headers['From'] = spec.get('from', DEFAULT_FROM)
            if isinstance(spec.get('to', []), basestring):
                recipients = set([spec.to])
            else:
                recipients = set(spec.to)

            #if data.config.testrun.owner:
            #    recipients.add(self.data.config.testrun.owner)
            #    headers['From'] = self.data.config.testrun.owner
            #    headers['Sender'] = DEFAULT_FROM

            assert recipients, "Please set the email section in the config file."
            if spec.get('reply-to'):
                headers['Reply-To'] = spec['reply-to']
            #else:
                #if self.data.config.testrun.owner:
                #    headers['Reply-To'] = self.data.config.testrun.owner

            #if spec.get('templates'):
            #    config_dir = os.path.dirname(self.data.config._filename)
            #    templates_dir = os.path.join(config_dir, spec.templates)
            #    loader = jinja2.FileSystemLoader(templates_dir)
            #else:
            loader = jinja2.PackageLoader(__package__)
            env = jinja2.Environment(loader=loader, autoescape=True)

            # Add custom filters
            env.filters['ljust'] = customfilter_ljust
            env.filters['rjust'] = customfilter_rjust
            env.filters['bzify'] = customfilter_bzify
            env.filters['product'] = customfilter_product

            template_subject = env.get_template('email_subject.tmpl')
            headers['Subject'] = template_subject.render(data=data, spec=spec)
            headers['To'] = list(recipients)

            #if int(self.data.result.bars.good_no_skips.percent_done) == 0:
            #    headers['Importance'] = 'high'

            msg = MIMEMultipart('alternative')
            for key, value in headers.items():
                if isinstance(value, (tuple, list)):
                    value = ','.join(value)
                msg.add_header(key, value)

            template_html = env.get_template('email_html.tmpl')
            html = template_html.render(dict(data=data))

            msg.attach(MIMEText(html.encode('utf-8'), 'html'))

            message = msg.as_string()
            yield AttrDict(headers=headers, body=message, text=html)

    def dump_text(self, email):
        path = self.data.session.path
        if os.path.exists(path):
            with open(os.path.join(path, DUMP_EMAIL_FILENAME), 'wt') as f:
                f.write(email.text.encode('utf-8'))

    def pytest_json_modifyreport(self, json_report):
        if self.enabled is False:
            return

        json_report['environment']['duts'] = list(self.duts_details())
        for dut in json_report['environment']['duts']:
            if dut.device.is_default:
                json_report['environment']['dut'] = dut

        json_report['environment']['config'] = self.context.get_config().api
        mail_host = self.options.get('server', MAIL_HOST)
        emails = self.compile_emails(json_report)

        server = None
        try:
            server = smtplib.SMTP(mail_host)
            for email in emails:
                server.sendmail(email.headers['From'], email.headers['To'],
                                email.body)
                LOG.info("Email report sent to: %s", email.headers['To'])
            # Dump the text version of the last email template
            #self.dump_text(email)
        finally:
            if server:
                server.quit()
