# Hack, hide DataLossWarnings
# Based on html5lib code namespaceHTMLElements=False should do it, but nope ...
# Also it doesn't seem to be available in older version from html5lib, removing it
import warnings
from typing import IO, Union

from bs4 import BeautifulSoup
from html5lib.constants import DataLossWarning

warnings.simplefilter('ignore', DataLossWarning)


def get_soup(obj: Union[str, IO, bytes], parser: str = 'html5lib') -> BeautifulSoup:
    return BeautifulSoup(obj, parser)
