# Writes a changelog in trac WikiFormatting based on a git log
from __future__ import unicode_literals, division, absolute_import

import codecs
from itertools import ifilter
import os
import re
import subprocess
import sys

from bs4 import BeautifulSoup
import dateutil.parser
import requests

visible_tags = [r'[fix]', r'[feature]', r'[tweak]', r'[enhancement]', r'[refactor]']
hidden_tags = ['[dev]']

out_path = 'ChangeLog'
if len(sys.argv) > 1:
    dir_name = os.path.dirname(sys.argv[1])
    if dir_name and not os.path.isdir(dir_name):
        print 'Output dir doesn\'t exist: %s' % sys.argv[1]
        sys.exit(1)
    out_path = sys.argv[1]

ua_response = requests.get('http://flexget.com/wiki/UpgradeActions')
ua_soup = BeautifulSoup(ua_response.text, 'html5lib')

# 1.0.3280 was last revision on svn
git_log_output = subprocess.check_output(['git', 'log', '--first-parent', '--topo-order', '--decorate=full',
                                          '--pretty=%n---%n.%d%n%ci%n%h%n%s%n%-b%n---%n', 'refs/tags/1.0.3280..HEAD'])
git_log_iter = ifilter(None, git_log_output.decode('utf-8').splitlines())

with codecs.open(out_path, 'w', encoding='utf-8') as out_file:
    for line in git_log_iter:
        assert line == '---'
        tag = re.search('refs/tags/([\d.]+)', next(git_log_iter))
        date = dateutil.parser.parse(next(git_log_iter))
        commit_hash = next(git_log_iter)
        commit_hash = '[https://github.com/Flexget/Flexget/commit/%s %s]' % (commit_hash, commit_hash)
        body = list(iter(git_log_iter.next, '---'))
        for visible_tag in visible_tags:
            regex = re.compile(visible_tag)
            match = regex.search(body[0])
            if match:
                break
        else:
            continue
        if tag:
            ver = tag.group(1)
            ua_link = ''
            result = ua_soup.find('h3', text=re.compile(' %s$' % re.escape(ver)))
            if result:
                ua_link = '^[wiki:UpgradeActions#%s upgrade actions]^ ' % result['id']
            out_file.write('\n=== %s (%s) %s===\n\n' % (ver, date.strftime('%Y.%m.%d'), ua_link))
        out_file.write(' * (%s) %s\n' % (commit_hash, '[[BR]]\n   '.join(body)))



