# Writes a changelog in trac WikiFormatting based on a git log
from __future__ import unicode_literals, division, absolute_import

import codecs
from itertools import ifilter
import os
import re
import subprocess
import sys

import dateutil.parser

out_path = 'ChangeLog'
if len(sys.argv) > 1:
    dir_name = os.path.dirname(sys.argv[1])
    if dir_name and not os.path.isdir(dir_name):
        print 'Output dir doesn\'t exist: %s' % sys.argv[1]
        sys.exit(1)
    out_path = sys.argv[1]
# 1.0.3280 was last revision on svn
git_log_output = subprocess.check_output(['git', 'log', '--pretty=%n---%n.%d%n%ci%n%h%n%s%n%-b%n---%n', '--topo-order', 'refs/tags/1.0.3280..HEAD'])
git_log_iter = ifilter(None, git_log_output.decode('utf-8').splitlines())

with codecs.open(out_path, 'w', encoding='utf-8') as out_file:
    for line in git_log_iter:
        assert line == '---'
        tag = re.search('tag: ([\d.]+)', next(git_log_iter))
        date = dateutil.parser.parse(next(git_log_iter))
        commit_hash = next(git_log_iter)
        body = list(iter(git_log_iter.next, '---'))
        if tag:
            out_file.write('\n=== %s (%s) ===\n\n' % (tag.group(1), date.strftime('%Y.%m.%d')))
        out_file.write(' * (%s) %s\n' % (commit_hash, '[[BR]]\n   '.join(body)))



