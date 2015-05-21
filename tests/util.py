"""
A method to create test-specific temporary directories
"""

from __future__ import unicode_literals, division, absolute_import
import inspect
import os
import shutil
import errno
import logging

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
    for frame_tuple in inspect.stack():
        frame = frame_tuple[0]
        # kludge, hunt callers upwards until we find our nose
        if frame.f_code.co_varnames and frame.f_code.co_varnames[0] == 'self':
            its_self = frame.f_locals['self']
            try:
                return its_self.id()
            except AttributeError:
                continue


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
