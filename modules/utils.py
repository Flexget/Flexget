import sgmllib

class HtmlParser(sgmllib.SGMLParser):
    from htmlentitydefs import entitydefs

    def __init__(self, s=None):
        sgmllib.SGMLParser.__init__(self)
        self.result = ''
        if s:
            self.feed(s)

    def handle_entityref(self, name):
        if self.entitydefs.has_key(name):
            x = ';'
        else:
            x = ''
        self.result = '%s&%s%s' % (self.result, name, x)

    def handle_data(self, data):
        if data:
            self.result += data

def html_decode(s):
    p = HtmlParser(s)
    return p.result
