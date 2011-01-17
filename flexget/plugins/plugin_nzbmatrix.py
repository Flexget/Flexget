import urllib2
import logging
import re
from flexget.plugin import *
import difflib
from flexget.utils.tools import urlopener

timeout = 10
import socket
socket.setdefaulttimeout(timeout)

log = logging.getLogger('nzbmatrix')


class NzbMatrix:
    """NZBMatrix search plugin."""
    
    def validator(self):        
        from flexget import validator
        root = validator.factory('dict')
        nzbmatrix = root.accept('dict', key='nzbmatrix')
        nzbmatrix.accept('number', key='catid')
        nzbmatrix.accept('number', key='num')
        nzbmatrix.accept('number', key='age')
        nzbmatrix.accept('choice', key='region').accept_choices(
            ['1', '2', '3', 'PAL', 'NTSC', 'FREE'], ignore_case=True)
        nzbmatrix.accept('text', key='group')
        nzbmatrix.accept('text', key='username', required=True)
        nzbmatrix.accept('text', key='apikey', required=True)
        nzbmatrix.accept('number', key='larger')
        nzbmatrix.accept('number', key='smaller')
        nzbmatrix.accept('number', key='minhits')
        nzbmatrix.accept('number', key='maxhits')
        nzbmatrix.accept('number', key='maxage')
        nzbmatrix.accept('boolean', key='englishonly')
        # TODO: I should overwrite this below. If there's an IMDB ID, I should 
        # search on it via weblink
        nzbmatrix.accept('choice', key='searchin').accept_choices(
            ['name', 'subject', 'weblink'], ignore_case=True)
        return root

    # Search plugin API
    def search(self, feed, entry):
        import urllib
        params = self.getparams(feed)
        params['search'] = self.clean(entry['title'])
        search_url = 'https://api.nzbmatrix.com/v1.1/search.php?' + \
                   urllib.urlencode(params)
        nzbid = self.nzbid_from_search(search_url, params['search'], entry)
        if nzbid == None:
            return
        else:
            download_params = {"username": params['username'], 
                      'apikey': params['apikey'],
                      'id': nzbid}
            return "http://api.nzbmatrix.com/v1.1/download.php?" + \
                                        urllib.urlencode(download_params)

    def getparams(self, feed):
        for cfg_entry in feed.config.get('search'):
            if isinstance(cfg_entry, dict) and 'nzbmatrix' in cfg_entry:
                config = cfg_entry['nzbmatrix']
                break
        # keeping vars seperate, for code readability. Config entries are
        # identical to params passed.
        params = config
        if 'searchin' in params:
            params['searchin'] = params['searchin'].lower()
        if 'region' in params:
            if params['region'].lower() == 'pal':
                params['region'] = 1
            if params['region'].lower() == 'ntsc':
                params['region'] = 2
            if params['region'].lower() == 'free':
                params['region'] = 3
        if 'englishonly' in params:
            if params['englishonly']:
                params['englishonly'] = 1
            else:
                del params['englishonly']
        return params
    
    def clean(self, s):
        """clean the title name for search"""
        #return s
        return s.replace('.', ' ').replace('_', ' ').replace(',', '')\
                         .replace('-', ' ').strip().lower()

    @internet(log)
    def nzbid_from_search(self, url, name, entry):
        """Parses nzb download url from api results"""
        import time
        import difflib
        log.debug("Sleeping to respect nzbmatrix rules about hammering the API")
        time.sleep(10)
        apireturn = self.parse_nzb_matrix_api(urlopener(url, log).read())
        if len(apireturn) == 0:
            return None
        else:
            names = []
            for result in apireturn:
                names.append(result["NZBNAME"])
            matches = difflib.get_close_matches(name, names, 1, 0.3)
            if len(matches) == 0:
                return None
            else:
                for result in apireturn:
                    if result["NZBNAME"] == matches[0]:
                        break
            if not "NZBID" in result:
                return None
            else:
                # Set the title to the title found
                entry["title"] = result["NZBNAME"]
                entry["content_size"] = int(float(result['SIZE']))
                entry["language"] = result['LANGUAGE']
                # Return an NZBID
                return result['NZBID']
                   
    def parse_nzb_matrix_api(self, apireturn):
        import re
        apireturn = str(apireturn)
        results = []
        api_result = {}
        apire = re.compile(r"([A-Z_]+):(.+);$")
        for line in apireturn.splitlines():
            match = apire.match(line)
            if not match and line == "|" and api_result != {}:
                #not an empty api result
                results.append(api_result)
                api_result = dict()
            elif match:
                api_result[match.group(1)] = match.group(2)
            else:
                log.debug("Recieved non-matching line in nzbmatrix API search: "
                          "%s" % line)
        if api_result != {}:
            results.append(api_result)
        return results

register_plugin(NzbMatrix, 'nzbmatrix', groups=['search'])
