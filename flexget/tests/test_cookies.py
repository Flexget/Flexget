from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest


class TestCookies(object):
    config = """
        tasks:
          test_cookies:
            text:
              url: http://httpbin.org/cookies
              entry:
                title: '\"title\": \"(.*)\"'
                url: '\"url\": \"(.*)\"'
            cookies: cookies.txt
    """

    @pytest.mark.online()
    def test_cookies(self, request, execute_task):
        task = execute_task('test_cookies', options={'nocache': True})
        assert task.find_entry(title='blah', url='aoeu'), 'Entry should have been created.'
