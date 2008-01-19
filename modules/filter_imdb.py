

import urllib
import urllib2
import urlparse
import logging
import re

# this way we don't force users to install bs incase they do not want to use module http
soup_present = True
soup_err = "Module filter_imdb requires BeautifulSoup. Please install it from http://www.crummy.com/software/BeautifulSoup/ or from your distribution repository."

try:
    from BeautifulSoup import BeautifulSoup
except:
    logging.warning(soup_err)
    soup_present = False

class ImdbParser:
    """Quick-hack to parse relevant imdb details"""
    
    def __init__(self):
        self.genres = []
        self.languages = []
        self.score = 0.0
        self.votes = 0
        self.year = 0
        self.plot_outline = None
        self.name = None

    def parse(self, url):
        logging.debug("ImdbParser parsing %s" % url)
        page = urllib2.urlopen(url)
        soup = BeautifulSoup(page)

        # get name
        tag_name = soup.find('h1')
        if tag_name != None:
            if tag_name.next != None:
                self.name = tag_name.next.string.strip()
                logging.debug("Detected name: %s" % self.name)
            
        # get votes
        tag_votes = soup.find(attrs={'href':'ratings', 'class': None})
        if tag_votes != None:
            str_votes = ''.join(c for c in tag_votes.string if c.encode().isdigit())
            self.votes = int(str_votes)
            logging.debug("Detected votes: %s" % self.votes)

        # get score
        tag_score = soup.find('b', text=re.compile('\d.\d/10'))
        if tag_score != None:
            str_score = tag_score.string
            re_score = re.compile("(\d.\d)\/10")
            match = re_score.search(str_score)
            if match != None:
                str_score = match.groups()[0]
                self.score = float(str_score)
                logging.debug("Detected score: %s" % self.score)

        # get genres
        for link in soup.findAll('a', attrs={'href': re.compile('^/Sections/Genres/')}):
            # skip links that have javascipr onclick (not in genrelist)
            if link.has_key('onclick'): continue
            self.genres.append(link.string.encode().lower())

        # get languages
        for link in soup.findAll('a', attrs={'href': re.compile('^/Sections/Languages/')}):
            lang = link.string.encode().lower()
            if not lang in self.languages:
                self.languages.append(lang)

        # get year
        tag_year = soup.find('a', attrs={'href': re.compile('^/Sections/Years/\d*')})
        if tag_year != None:
            self.year = int(tag_year.string)
            logging.debug("Detected year: %s" % self.year)

        # get plot outline
        tag_outline = soup.find('h5', text='Plot Outline:')
        if not tag_outline:
            tag_outline = soup.find('h5', text='Plot Summary:')
        if tag_outline:
            if tag_outline.next != None:
                self.plot_outline = tag_outline.next.string.strip()
                logging.debug("Detected plot outline: %s" % self.plot_outline)

        logging.debug("Detected genres: %s" % self.genres)
        logging.debug("Detected languages: %s" % self.languages)

class FilterImdb:

    """
        This module allows filtering based on IMDB score, votes and genres etc.

        Results are cached so modifying configuration does not have an effect
        on already filtered entries. This is done to reduce traffic to
        IMDB now only once per movie. You can disable this TEMPORARILY by using
        --no-cache argument. This will potentially affect other modules aswell.

        Configuration:
        
            Note: All parameters are optional. Some are mutually exclusive.
        
            min_score: <num>
            min_votes: <num>
            min_year: <num>

            # reject if genre contains any of these
            reject_genres:
                - genre1
                - genre2

            # reject if language contain any of these
            reject_languages:
                - language1

            # accept only this language
            accept_languages:
                - language1

            # reject all entries which are not imdb-compatible
            # this has default value (True) even when key not present
            reject_invalid: True / False

        Entry fields (module developers):
        
            All fields are optional, but lack of required fields will
            result in filtering usually in default configuration (see reject_invalid).
        
            imdb_url       : Most important field, should point to imdb-movie-page (string)
            imdb_score     : Pre-parsed score/rating value (float)
            imdb_votes     : Pre-parsed number of votes (int)
            imdb_year      : Pre-parsed production year (int)
            imdb_genres    : Pre-parsed genrelist (array)
            imdb_languages : Pre-parsed languagelist (array)
            
            Supplying pre-parsed values may avoid checking and parsing from imdb_url.
            So supply them in your input-module if it's practical!
    """

    def register(self, manager, parser):
        manager.register(instance=self, type='filter', keyword='imdb', callback=self.run)

    def imdb_required(self, entry, config):
        """Return True if config contains conditions that are not available in preparsed fields"""
        # TODO: make dict (mapping min_votes <->imdb_votes) and loop it
        # check that entry values are VALID (None is considered as having value, this is a small bug!)
        if config.has_key('min_votes') and not entry.has_key('imdb_votes'): return True
        if config.has_key('min_score') and not entry.has_key('imdb_score'): return True
        if config.has_key('min_year') and not entry.has_key('imdb_year'): return True
        if config.has_key('reject_genres') and not entry.has_key('imdb_genres'): return True
        if config.has_key('reject_languages') and not entry.has_key('imdb_languages'): return True
        if config.has_key('accept_languages') and not entry.has_key('imdb_languages'): return True
        return False

    def run(self, feed):
        if not soup_present: raise Exception(soup_err)

        config = feed.config['imdb']

        for entry in feed.entries:

            if entry.get('imdb_url', None) == None and self.imdb_required(entry, config):
                if config.get('reject_invalid', True):
                    logging.debug("FilterImdb rejecting %s due required missing imdb url and configuration conditions" % entry['title'])
                    feed.filter(entry)
                else:
                    logging.debug("FilterImdb unable to check %s due missing imdb url, configured to accept (reject_invalid is False)" % entry['title'])
                continue

            # do not check again from imdb if this has already been checked
            if entry.has_key('imdb_url'):
                # disable cache on --no-cache
                if feed.cache.get(entry['imdb_url'], False) and not feed.manager.options.nocache:
                    logging.debug('FilterImdb filtering %s, it has already been tried before' % entry['title'])
                    feed.filter(entry)
                    continue

            imdb = ImdbParser()
            if self.imdb_required(entry, config):
                imdb.parse(entry['imdb_url'])
                feed.cache.store(entry['imdb_url'], True, 90)
            else:
                # Set few required fields manually from entry, and thus avoiding request & parse
                # Note: It doesn't matter even if some fields are missing, previous imdb_required
                # checks that those aren't required in condition check. So just set them all! :)
                imdb.votes = entry.get('imdb_votes', 0)
                imdb.score = entry.get('imdb_score', 0.0)
                imdb.year = entry.get('imdb_year', 0)
                imdb.languages = entry.get('imdb_languages', [])
                imdb.genres = entry.get('imdb_genres', [])

            # Check defined conditions
            
            fail = False
            if config.has_key('min_score'):
                if imdb.score < config['min_score']:
                    logging.debug("FilterImdb rejecting %s due min_score" % entry['title'])
                    fail = True
            if config.has_key('min_votes'):
                if imdb.votes < config['min_votes']:
                    logging.debug("FilterImdb rejecting %s due min_votes" % entry['title'])
                    fail = True
            if config.has_key('min_year'):
                if imdb.year < config['min_year']:
                    logging.debug("FilterImdb rejecting %s due min_year" % entry['title'])
                    fail = True
            if config.has_key('reject_genres'):
                rejected = config['reject_genres']
                for genre in imdb.genres:
                    if genre in rejected:
                        logging.debug("FilterImdb rejecting %s due reject_genres" % entry['title'])
                        fail = True
                        break
            if config.has_key('reject_languages'):
                rejected = config['reject_languages']
                for language in imdb.languages:
                    if language in rejected:
                        logging.debug("FilterImdb rejecting %s due reject_languages" % entry['title'])
                        fail = True
                        break
            if config.has_key('accept_languages'):
                accepted = config['accept_languages']
                for language in imdb.languages:
                    if language not in accepted:
                        logging.debug("FilterImdb rejecting %s due accept_languages" % entry['title'])
                        fail = True
                        break

            # populate some fields from imdb results, incase someone wants to use them later
            entry['imdb_plot_outline'] = imdb.plot_outline
            entry['imdb_name'] = imdb.name

            if fail:
                logging.debug("FilterImdb filtering %s" % (entry))
                feed.filter(entry)

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)

#    i = ImdbParser('http://www.imdb.com/title/tt0245429/')
#    i.parse()

    from test_tools import MockFeed
    feed = MockFeed()

    """
    dummy = {}
    dummy['title'] = 'dummy title'
    dummy['url'] = 'http://127.0.0.1/dummy'
    dummy['imdb_url'] = 'http://www.imdb.com/title/tt0245429/'
    dummy['imdb_score'] = 5.2
    dummy['imdb_votes'] = 1253
    #dummy['imdb_genres'] = ['comedy']
    """
    dummy = {}
    dummy['title'] = 'imdb dummy title'
    dummy['url'] = 'http://127.0.0.1/dummy'
    dummy['imdb_url'] = sys.argv[1]
    
    feed.entries = []
    feed.entries.append(dummy)

    config = {}
    config['min_votes'] = 200000
    #config['min_score'] = 9.5
    config['reject_genres'] = ['animation']
    #config['reject_languages'] = ['japanese']

    feed.config['imdb'] = config

    f = FilterImdb()
    f.run(feed)

    import yaml
    print "-"*60
    print yaml.safe_dump(feed.entries)
    print "-"*60
#    print yaml.safe_dump(feed.session)

