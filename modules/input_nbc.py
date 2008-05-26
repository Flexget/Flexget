import urllib2
from feed import Entry
import re

"""Get Heroes novels from nbc.com"""

class InputNBC:
    def register(self, manager, parser):
        manager.register(event="input", keyword="nbc", callback=self.run)

    def run(self, feed):
        f = urllib2.urlopen("http://www.nbc.com/Heroes/js/novels.js")
        s = f.read()
        l = s.split("\r\n")

        for line in l:
            # title
            m = re.search('novelTitle = "(.*)"', line)
            if m:
                title = m.group(1)
            m = re.search('novelPrint = "(.*)"', line)
            if m:
                url = "http://www.nbc.com"+m.group(1)
            if line.strip() == 'break':
                e = Entry(title, url)
                feed.entries.append(e)
            if line.strip() == 'default:':
                break
