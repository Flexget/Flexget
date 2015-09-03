

import sys
import os

if not sys.platform.startswith('win'):
    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        data_files = [('/etc/bash_completion.d', ['extras/completion/flexget'])]
        print('root')
    print('not win')
