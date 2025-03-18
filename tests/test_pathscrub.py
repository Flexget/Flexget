import pytest

from flexget.utils.pathscrub import pathscrub


class TestPathscrub:
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
            'aoeu. > * . * <': 'aoeu',  # Really don't leave spaces or dots at the end
        }
        for test, value in win_fn.items():
            result = pathscrub(test, os='windows', filename=True)
            assert result == value, f'{result} != {value}'

    def test_windows_paths(self):
        win_path = {
            'aoeu/aoeu': 'aoeu/aoeu',  # Don't strip slashes in path mode
            'aoeu\\aoeu': 'aoeu\\aoeu',  # Or backslashes
            'aoeu / aoeu ': 'aoeu/aoeu',  # Don't leave spaces at the begin or end of folder names
            'aoeu \\aoeu ': 'aoeu\\aoeu',
            'aoeu./aoeu.\\aoeu.': 'aoeu/aoeu\\aoeu',  # Or dots
        }
        for test, value in win_path.items():
            result = pathscrub(test, os='windows', filename=False)
            assert result == value, f'{result} != {value}'

    def test_degenerate(self):
        # If path is reduced to nothing, make sure it complains
        with pytest.raises(
            ValueError,
            match='Nothing was left after stripping invalid characters from path `<<<<:>>>>`!',
        ):
            pathscrub('<<<<:>>>>', os='windows', filename=True)

    def test_space_around(self):
        # We don't want folder or file names to end or start with spaces on any platform
        space_paths = {' / aoeu /aoeu ': '/aoeu/aoeu', '/   a/a   ': '/a/a', '/a  /': '/a/'}
        for platform in ['windows', 'linux', 'mac']:
            for test, value in space_paths.items():
                result = pathscrub(test, filename=False)
                assert result == value, f'{result} != {value} ({platform})'

        # Windows only should also use backslashes as dir separators
        test = ['c:\\ aoeu \\aoeu /aoeu ', 'c:\\aoeu\\aoeu/aoeu']
        result = pathscrub(test[0], os='windows', filename=False)
        assert result == test[1], f'{result} != {test[1]}'
