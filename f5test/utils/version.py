#!/bin/env python
import re
import functools
from itertools import izip_longest, chain


class InvalidVersionString(Exception):
    """Raised when invalid version strings are used.
    """


class IllegalComparison(Exception):
    """Raised when invalid version strings are used.
    """


def py2x_cmp(a, b):
    return (a > b) - (a < b)


class Product(object):
    """Normalized product."""
    EM = 'em'
    BIGIP = 'bigip'
    WANJET = 'wanjet'
    ARX = 'arx'
    SAM = 'sam'
    BIGIQ = 'bigiq'
    NSX = 'nsx'
    APIC = 'apic'
    IWORKFLOW = 'iworkflow'

    def __init__(self, product_string):
        """String to Product class converter.

        >>> Product('EM 1.2')
        em
        >>> Product('Enterprise Manager')
        em
        >>> Product('BIG-IP_v9.3.1')
        bigip
        >>> Product('BIGIP')
        bigip
        """
        if re.search("(?:EM|Enterprise Manager)", str(product_string), re.IGNORECASE):
            self.product = Product.EM
        elif re.search("BIG-?IP", str(product_string), re.IGNORECASE):
            self.product = Product.BIGIP
        elif re.search("BIG-?IQ", str(product_string), re.IGNORECASE):
            self.product = Product.BIGIQ
        elif re.search("(?:WANJET|WJ)", str(product_string), re.IGNORECASE):
            self.product = Product.WANJET
        elif re.search("ARX", str(product_string), re.IGNORECASE):
            self.product = Product.ARX
        elif re.search("BIG-IP_SAM", str(product_string), re.IGNORECASE):
            self.product = Product.SAM
        elif re.search("NSX", str(product_string), re.IGNORECASE):
            self.product = Product.NSX
        elif re.search("APIC", str(product_string), re.IGNORECASE):
            self.product = Product.APIC
        elif re.search("iWorkflow", str(product_string), re.IGNORECASE):
            self.product = Product.IWORKFLOW
        else:
            self.product = ''

    @property
    def is_bigip(self):
        return self.product == Product.BIGIP

    @property
    def is_bigiq(self):
        return self.product == Product.BIGIQ

    @property
    def is_em(self):
        return self.product == Product.EM

    @property
    def is_wanjet(self):
        return self.product == Product.WANJET

    @property
    def is_sam(self):
        return self.product == Product.SAM

    @property
    def is_apic(self):
        return self.product == Product.APIC

    # TODO: need to remove self.product == Product.BIGIQ when iWorkflow name change happens.
    @property
    def is_iworkflow(self):
        return self.product == Product.IWORKFLOW

    @property
    def is_none(self):
        return self.product == ''

    @property
    def to_tmos(self):
        if self.product == Product.EM:
            return 'EM'
        elif self.product == Product.BIGIP:
            return 'BIG-IP'
        elif self.product == Product.BIGIQ:
            return 'BIG-IQ'
        elif self.product == Product.IWORKFLOW:
            return 'iWorkflow'
        else:
            return str(self).upper()

    def __cmp__(self, other):
        if not isinstance(other, Product):
            other = Product(other)

        return py2x_cmp(self.product, other.product)

    def __repr__(self):
        return self.product

    def __int__(self):
        return ['',
                Product.EM,
                Product.BIGIP,
                Product.BIGIQ,
                Product.WANJET,
                Product.ARX,
                Product.SAM,
                Product.IWORKFLOW].index(self.product)

    __hash__ = __int__


class Version(object):
    """Generic Version + Build object.
    Samples:

    >>> Version('1.1')
    <Version: 1.1.0 0.0.0>
    >>> Version('9.3.1')
    <Version: 9.3.1 0.0.0>
    >>> Version('9.3.1 650.0')
    <Version: 9.3.1 650.0.0>
    >>> Version('11.0.1 build6901.45.4')
    <Version: 11.0.1 6901.45.4>
    >>> Version('11.0.1') > '9.3.0'
    True
    >>> Version('9.3.1') > '9.3.1 1.0'
    False
    >>> Version('bigip 9.3.1') > 'em 1.8'
    False
    >>> Version('bigip 9.3.1') < 'em 1.8'
    False

    etc..
    """
    def __init__(self, version=None, product=None):
        self.version_digits = []
        self.build_digits = []

        if isinstance(version, Version):
            self.version_digits[:] = version.version_digits[:]
            self.build_digits[:] = version.build_digits[:]
            self.product = version.product
        else:
            mo = re.search("(?=\d)([\d\.\s\-]+)", str(version), re.IGNORECASE)

            if mo is None:
                self.version_digits[:] = (0,) * 3
                self.build_digits[:] = (0,) * 3
            else:
                ret = re.split('[\s\-]+', mo.group(0), 1)
                self.version_digits[:] = [int(x) for x in re.split('[\D]+', ret[0]) if x]
                if len(ret) > 1:
                    self.build_digits[:] = [int(x) for x in re.split('[\D]+', ret[1]) if x]
                else:
                    self.build_digits[:] = (0,) * 3

            if product:
                self.product = Product(product)
            else:
                self.product = Product(version)

    def __abs__(self):
        tmp = Version(self)
        tmp.build_digits[:] = (0,) * 3
        return tmp

    def __eq__(self, other):
        result = self._cmp(other)
        if result is None:
            return False
        else:
            return result == 0

    def __ne__(self, other):
        result = self._cmp(other)
        if result is None:
            return False
        else:
            return result != 0

    def __lt__(self, other):
        result = self._cmp(other)
        if result is None:
            return False
        else:
            return result < 0

    def __le__(self, other):
        result = self._cmp(other)
        if result is None:
            return False
        else:
            return result <= 0

    def __gt__(self, other):
        result = self._cmp(other)
        if result is None:
            return False
        else:
            return result > 0

    def __ge__(self, other):
        result = self._cmp(other)
        if result is None:
            return False
        else:
            return result >= 0

    def __nonzero__(self):
        return not self.is_none

    def _cmp(self, other):
        """Easy comparison with like-objects or other strings"""

        if not isinstance(other, Version):
            other = Version(other)

        if (self.product is None and other.product is not None) or \
           (self.product is not None and other.product is None):
            raise IllegalComparison("Product is missing from one of the versions.")

        if self.product != other.product:
            return None

        pairs = chain(
            izip_longest(self.version_digits, other.version_digits, fillvalue=0),
            izip_longest(self.build_digits, other.build_digits, fillvalue=0),
        )
        return functools.reduce(lambda s, x: s or py2x_cmp(*x), pairs, 0)

    @property
    def is_none(self):
        return not any(self.version_digits + self.build_digits)

    @property
    def version(self):
        if self.is_none:
            return ''
        return '.'.join(map(str, self.version_digits))

    @property
    def build(self):
        if self.is_none:
            return ''
        return '.'.join(map(str, self.build_digits))

    def __repr__(self):
        if self.is_none:
            return '<Version: None>'

        dots = '.'.join(str(self.version_digits))
        if self.build_digits:
            dots += ' ' + '.'.join(str(self.build_digits))
        if self.product.is_none:
            return "<Version: %s>" % dots
        return "<Version: {0} {1}>".format(self.product, dots)

    def __str__(self):
        if self.is_none:
            return ''
        bits = []
        if self.product:
            bits.append(self.product.to_tmos)
        bits.append(self.version)
        bits.append(self.build)
        return ' '.join(bits)

    def __int__(self):
        total = 0
        for i, x in enumerate(reversed(self.version_digits + self.build_digits)):
            total += int(x) * 10 ** i
        total += int(self.product) * 10 ** (i + 1)
        return total

    __hash__ = __int__


if __name__ == '__main__':

    assert Version('BigIP').is_none
    assert not Version("10.1.1") < '9.4.8'
    assert Version("iWorkflow 2.2") < 'iWorkflow 2.2.0 0.0.10541'
    assert not Version("12.2") > '12.2.0 1.0.10'
    assert not Version("9.4.8 1.0") < Version('9.4.8')
    assert Version("BIGIP 13.1.1-1001.0") > Version('BiGiP  9.4.8')
    assert Version("BIGIP 13.0.0 1.0") > Version('BIGIP 13.0.0')
    assert Version("9.4.8 1.0") < '9.4.8 3.0'
    assert not Version("11.0.0 6900.0") <= '10.2.1 397.0.1'
    assert not Version("BIGIP 12.1.2.1") > 'BIGIP 13.0.0'
    assert Version('BigIP 12.3.4.1 0.0.1 HF4').build == '0.0.1'
    assert Version('BigIP 12.3.4.1').version == '12.3.4.1'
    print 'Cool!'
