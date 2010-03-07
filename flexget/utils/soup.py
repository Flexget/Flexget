import html5lib
from html5lib import treebuilders
from cStringIO import StringIO

# Hack, hide DataLossWarnings
# Based on html5lib code namespaceHTMLElements=False should do it, but nope ...
# Also it doesn't seem to be available in older version from html5lib, removing it
import warnings
from html5lib.constants import DataLossWarning
warnings.simplefilter('ignore', DataLossWarning)


def get_soup(obj):
    if isinstance(obj, basestring):
        obj = StringIO(obj)
    parser = html5lib.HTMLParser(tree=treebuilders.getTreeBuilder('beautifulsoup'))
    return parser.parse(obj.read())
