from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from bs4 import BeautifulSoup

# Hack, hide DataLossWarnings
# Based on html5lib code namespaceHTMLElements=False should do it, but nope ...
# Also it doesn't seem to be available in older version from html5lib, removing it
import warnings
from html5lib.constants import DataLossWarning
warnings.simplefilter('ignore', DataLossWarning)


def get_soup(obj, parser='html5lib'):
    return BeautifulSoup(obj, parser)
