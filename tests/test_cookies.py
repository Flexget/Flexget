from __future__ import unicode_literals, division, absolute_import


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

    def test_cookies(self, execute_task, use_vcr):
        task = execute_task('test_cookies', options={'nocache': True})
        assert task.find_entry(title='blah', url='aoeu'), 'Entry should have been created.'
