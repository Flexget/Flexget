import os, html5lib, urllib2
from html5lib import treebuilders
from cStringIO import StringIO

class TestHtml5Lib():
    def testParseBroken(self):
        parser = html5lib.HTMLParser(tree=treebuilders.getTreeBuilder('beautifulsoup'))
        s = StringIO("""<html>
<head><title>Foo</title>
<body>
<p class=foo><b>Some Text</b>
<p><em>Some Other Text</em>""")
        soup = parser.parse(s)

        body = soup.find('body')
        ps = body.findAll('p')
        assert ps[0].parent.name == 'body'
        assert ps[1].parent.name == 'body'
        b = soup.find('b')
        assert b.parent.name == 'p'
        em = soup.find('em')
        assert em.parent.name == 'p'

        assert soup.find('p', attrs={'class': 'foo'})
