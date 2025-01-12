# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "gitpython ~=3.1",
# ]
# ///

import collections
import contextlib
import re
import sys
from collections.abc import Generator, Iterable
from typing import Optional

from git import Repo


class MDChangeSet:
    """Represents a markdown change-set for a single version."""

    CATEGORIES = [
        ('### Added\n', ['add', 'added', 'feature']),
        ('### Changed\n', ['change', 'changed', 'update']),
        ('### Fixed\n', ['fix', 'fixed']),
        ('### Deprecated\n', ['deprecate', 'deprecated']),
        ('### Removed\n', ['remove', 'removed']),
    ]

    def __init__(self) -> None:
        self.pre_header = ['\n']
        self.version_header = ''
        self.post_header: list[str] = []
        self.sections: collections.OrderedDict[str, list[str]] = collections.OrderedDict()
        self.footer: list[str] = []

    @classmethod
    def from_md_lines(cls, lines):
        """Parse an existing markdown changeset section and return the VersionLog instance."""
        instance = cls()
        instance.pre_header, version_header, tail = isplit('## ', lines)
        if version_header:
            instance.version_header = version_header
        instance.post_header, section, tail = isplit('### ', tail)
        while section:
            instance.sections[section], section, tail = isplit('### ', tail)
        return instance

    def parse_message(self, message: str) -> bool:
        """
        Parses a git commit message and formats and adds any tagged messages to this changeset.
        Returns True if one or more changelog messages was found.
        """
        found = False
        for cat, item in self.change_items(message):
            found = True
            item = re.sub(
                r'#(\d{3,4})', r'[#\1](https://github.com/Flexget/Flexget/issues/\1)', item
            )
            item = f'- {item}\n'
            self.sections.setdefault(cat, ['\n']).insert(0, item)
        return found

    def change_items(self, message: str):
        """An iterator of changelog updates from a commit message in the form (category, message)"""
        for line in message.split('\n'):
            for cat_match in re.finditer(r'\[(\w+)\]', line):
                found_cat = self.cat_lookup(cat_match.group(1))
                if found_cat:
                    line = line.replace(cat_match.group(0), '').strip()
                    yield found_cat, line

    def cat_lookup(self, cat: str) -> Optional[str]:
        """Return an official category for `cat` tag text."""
        for cat_item in self.CATEGORIES:
            if cat.lower() in cat_item[1]:
                return cat_item[0]
        return None

    def to_md_lines(self) -> Generator[str, None, None]:
        """An iterator over the markdown lines representing this changeset."""
        yield from self.pre_header
        yield self.version_header
        yield from self.post_header
        for section, items in self.sections.items():
            yield section
            yield from items
        yield from self.footer


def isplit(
    start_text: str, iterator: Iterable[str]
) -> tuple[list[str], Optional[str], Iterable[str]]:
    """Returns head, match, tail tuple, where match is the first line that starts with `start_text`"""
    head: list[str] = []
    iterator = iter(iterator)
    for item in iterator:
        if item.startswith(start_text):
            return head, item, iterator
        head.append(item)
    return head, None, iterator


if __name__ == '__main__':
    try:
        filename = sys.argv[1]
    except IndexError:
        print('No filename specified, using changelog.md')
        filename = 'changelog.md'
    with open(filename, encoding='utf-8') as logfile:
        pre_lines, start_comment, tail = isplit('<!---', logfile)
        active_lines, end_comment, tail = isplit('<!---', tail)
        post_lines = list(tail)

    repo = Repo('.')
    cur_ver = MDChangeSet.from_md_lines(active_lines)
    latestref = re.match(r'<!---\s*([\d\w]+)', start_comment).group(1)
    oldestref = re.match(r'<!---\s*([\d\w]+)', end_comment).group(1)
    released_vers: list[MDChangeSet] = []
    commits = list(repo.iter_commits(f'{latestref}..HEAD', reverse=True))
    modified = False
    if commits:
        tags = {}
        for tag in repo.tags:
            tags[tag.commit.hexsha] = tag
        for commit in commits:
            if cur_ver.parse_message(commit.message):
                modified = True
            if commit.hexsha in tags:
                modified = True
                # Tag changeset with release date and version and create new current changeset
                tag_name = tags[commit.hexsha].name
                version = tag_name.lstrip('v')
                release_date = tags[commit.hexsha].commit.committed_datetime.strftime('%Y-%m-%d')
                cur_ver.version_header = f'## {version} ({release_date})\n'
                diffstartref = oldestref
                if oldestref in tags:
                    diffstartref = tags[oldestref].name
                cur_ver.post_header.insert(
                    0,
                    '[all commits]'
                    f'(https://github.com/Flexget/Flexget/compare/{diffstartref}...{tag_name})\n',
                )
                released_vers.insert(0, cur_ver)
                cur_ver = MDChangeSet()
                oldestref = commit.hexsha

            verfile = repo.tree('HEAD')['flexget/_version.py'].data_stream.read()
            __version__: Optional[str] = None
            with contextlib.suppress(Exception):
                exec(verfile)
            new_version_header = f'## {__version__} (unreleased)\n'
            if new_version_header != cur_ver.version_header:
                cur_ver.version_header = new_version_header
                modified = True

    if modified:
        print('Writing modified changelog.')
        with open(filename, 'w', encoding='utf-8') as logfile:
            logfile.writelines(pre_lines)
            logfile.write(f'<!---{commit.hexsha}--->\n')
            logfile.writelines(cur_ver.to_md_lines())
            logfile.write(f'<!---{oldestref}--->\n')
            for ver in released_vers:
                logfile.writelines(ver.to_md_lines())
            logfile.writelines(post_lines)
    else:
        print('No updates to write.')
