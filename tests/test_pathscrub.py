from __future__ import unicode_literals, division, absolute_import

from nose.tools import assert_raises

from flexget.utils.pathscrub import pathscrub


class TestPathscrub(object):
    def test_windows_filenames(self):
        # Windows filename tests
        # 'None' indicates there should be no changes after path scrub
        win_fn = {
            'afilename': 'afilename',
            'filename/with/slash': 'filename with slash',
            'filename\\with\\backslash': 'filename with backslash',
            'afilename.': 'afilename',  # filenames can't end in dot
            'a<b>c:d"e/f\\g|h?i*j': 'a b c d e f g h i j',  # Can't contain invalid characters
            'a<<b?*?c: d': 'a b c d',  # try with some repeated bad characters
            'something.>': 'something',  # Don't leave dots at the end
            'something *': 'something',  # Don't leave spaces at the end
            'aoeu. > * . * <': 'aoeu'  # Really don't leave spaces or dots at the end
        }
        for test in win_fn:
            result = pathscrub(test, os='windows', filename=True)
            assert result == win_fn[test], '%s != %s' % (result, win_fn[test])

    def test_windows_paths(self):
        win_path = {
            'aoeu/aoeu': 'aoeu/aoeu',  # Don't strip slashes in path mode
            'aoeu\\aoeu': 'aoeu\\aoeu',  # Or backslashes
            'aoeu /aoeu ': 'aoeu/aoeu',  # Don't leave spaces at the end of folder names
            'aoeu \\aoeu ': 'aoeu\\aoeu',
            'aoeu./aoeu.\\aoeu.': 'aoeu/aoeu\\aoeu'  # Or dots
        }
        for test in win_path:
            result = pathscrub(test, os='windows', filename=False)
            assert result == win_path[test], '%s != %s' % (result, win_path[test])

    def test_degenerate(self):
        # If path is reduced to nothing, make sure it complains
        assert_raises(ValueError, pathscrub, '<<<<:>>>>', os='windows', filename=True)

