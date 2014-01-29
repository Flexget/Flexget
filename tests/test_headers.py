from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from nose.plugins.attrib import attr

class TestHeaders(FlexGetBase):
    __yaml__ = """
        tasks:
          test_headers:
            text:
              url: http://httpbin.org/cookies
              entry:
                title: '\"title\": \"(.*)\"'
                url: '\"url\": \"(.*)\"'
            headers:
              Cookie: "title=blah; url=other"
    """

    @attr(online=True)
    def test_headers(self):
        self.execute_task('test_headers', options={'nocache': True})
        assert self.task.find_entry(title='blah', url='other'), 'Entry should have been created.'
