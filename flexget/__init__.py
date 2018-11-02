# #!/usr/bin/python
from __future__ import unicode_literals, division, absolute_import, print_function
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget._version import __version__  # noqa
from flexget import cli


if __name__ == "__main__":
    cli.main()
