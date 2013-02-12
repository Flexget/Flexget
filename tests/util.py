"""
A method to create test-specific temporary directories
"""

from __future__ import unicode_literals, division, absolute_import
import sys
import os
import shutil
import errno
import logging
import time
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('tests.util')


def mkdir(*a, **kw):
    try:
        os.mkdir(*a, **kw)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass
        else:
            raise


def find_test_name():
    try:
        from nose.case import Test
        from nose.suite import ContextSuite
        import types

        def get_nose_name(its_self):
            if isinstance(its_self, Test):
                file_, module, class_ = its_self.address()
                name = '%s:%s' % (module, class_)
                return name
            elif isinstance(its_self, ContextSuite):
                if isinstance(its_self.context, types.ModuleType):
                    return its_self.context.__name__
    except ImportError:
        # older nose
        from nose.case import FunctionTestCase, MethodTestCase
        from nose.suite import TestModule
        from nose.util import test_address

        def get_nose_name(its_self):
            if isinstance(its_self, (FunctionTestCase, MethodTestCase)):
                file_, module, class_ = test_address(its_self)
                name = '%s:%s' % (module, class_)
                return name
            elif isinstance(its_self, TestModule):
                return its_self.moduleName

    i = 0
    while True:
        i += 1
        frame = sys._getframe(i)
        # kludge, hunt callers upwards until we find our nose
        if (frame.f_code.co_varnames
            and frame.f_code.co_varnames[0] == 'self'):
            its_self = frame.f_locals['self']
            name = get_nose_name(its_self)
            if name is not None:
                return name


def maketemp(name=None):
    tmp = os.path.join(os.path.dirname(__file__), 'tmp')
    mkdir(tmp)

    if not name:
        # Colons are not valid characters in directories on Windows
        name = find_test_name().replace(':', '_')

    # Always use / instead of \ to avoid escaping issues
    tmp = os.path.join(tmp, name).replace('\\', '/')
    log.trace("Creating empty tmpdir %r" % tmp)
    try:
        shutil.rmtree(tmp)
    except OSError as e:
        if e.errno == errno.ENOENT:
            pass
        else:
            raise
    os.mkdir(tmp)
    return tmp
