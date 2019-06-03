from __future__ import absolute_import, division, unicode_literals

# Hack, hide DataLossWarnings
# Based on html5lib code namespaceHTMLElements=False should do it, but nope ...
# Also it doesn't seem to be available in older version from html5lib, removing it
import warnings
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from bs4 import BeautifulSoup
from html5lib.constants import DataLossWarning

warnings.simplefilter('ignore', DataLossWarning)


def get_soup(obj, parser='html5lib'):
    return BeautifulSoup(obj, parser)
