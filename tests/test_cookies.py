from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from nose.plugins.attrib import attr

class TestCookies(FlexGetBase):
    __yaml__ = """
        tasks:
          test_cookies:
            text:
              url: http://httpbin.org/cookies
              entry:
                title: '\"title\": \"(.*)\"'
                url: '\"url\": \"(.*)\"'
            cookies: cookies.txt
    """

    @attr(online=True)
    def test_cookies(self):
        self.execute_task('test_cookies', options={'nocache': True})
        assert self.task.find_entry(title='blah', url='aoeu'), 'Entry should have been created.'
