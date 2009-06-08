import html5lib
from html5lib import treebuilders
from cStringIO import StringIO

def get_soup(obj):
    if isinstance(obj, basestring):
        obj = StringIO(obj)
    parser = html5lib.HTMLParser(tree=treebuilders.getTreeBuilder('beautifulsoup'))
    return parser.parse(obj)
