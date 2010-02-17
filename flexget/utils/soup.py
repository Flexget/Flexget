import html5lib
from html5lib import treebuilders
from cStringIO import StringIO

# Hack, hide DataLossWarnings
# Based on html5lib code namespaceHTMLElements=False should do it, but nope ...
import warnings
from html5lib.constants import DataLossWarning
warnings.simplefilter('ignore', DataLossWarning)


def get_soup(obj):
    if isinstance(obj, basestring):
        obj = StringIO(obj)
    parser = html5lib.HTMLParser(namespaceHTMLElements=False, tree=treebuilders.getTreeBuilder('beautifulsoup'))
    return parser.parse(obj)
