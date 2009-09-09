import logging
from flexget.plugin import *
from flexget.utils.log import log_once

log = logging.getLogger('imdb')

class FilterImdb:
    """
        This plugin allows filtering based on IMDB score, votes and genres etc.

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
    """
    
    def validator(self):
        """Validate given configuration"""
        from flexget import validator
        imdb = validator.factory('dict')
        imdb.accept('number', key='min_year')
        imdb.accept('number', key='min_votes')
        imdb.accept('decimal', key='min_score')
        imdb.accept('list', key='reject_genres').accept('text')
        imdb.accept('list', key='reject_languages').accept('text')
        imdb.accept('list', key='accept_languages').accept('text')
        return imdb

    def imdb_required(self, entry, config):
        """Return True if config contains conditions that are NOT available in preparsed fields"""
        check = {'min_votes':'imdb_votes', 'min_year':'imdb_year', 'min_score': 'imdb_score', 
                 'reject_genres': 'imdb_genres', 'reject_languages': 'imdb_languages', 
                 'accept_languages': 'imdb_languages'}
        for key, value in check.iteritems():
            if key in config and not value in entry: 
                return True
        return False

    def feed_filter(self, feed):
        config = feed.config['imdb']
        
        lookup = get_plugin_by_name('imdb_lookup').instance.lookup
        
        for entry in feed.entries:
            
            if self.imdb_required(entry, config):
                try:
                    lookup(feed, entry)
                except PluginError, e:
                    log.error('Skipping %s because error: %s' % (entry['title'], e.value))
                    continue
            else:
                # Set few required fields manually from entry, and thus avoiding request & parse
                # Note: It doesn't matter even if some fields are missing, previous imdb_required
                # checks that those aren't required in condition check. So just set them all! :)
                log.debug('no imdb request needed')
                imdb.votes = entry.get('imdb_votes', 0)
                imdb.score = entry.get('imdb_score', 0.0)
                imdb.year = entry.get('imdb_year', 0)
                imdb.languages = entry.get('imdb_languages', [])
                imdb.genres = entry.get('imdb_genres', [])
            
            # Check defined conditions, TODO: rewrite into functions?
            reasons = []
            if 'min_score' in config:
                if entry['imdb_score'] < config['min_score']:
                    reasons.append('min_score (%s < %s)' % (entry['imdb_score'], config['min_score']))
            if 'min_votes' in config:
                if entry['imdb_votes'] < config['min_votes']:
                    reasons.append('min_votes (%s < %s)' % (entry['imdb_votes'], config['min_votes']))
            if 'min_year' in config:
                if entry['imdb_year'] < config['min_year']:
                    reasons.append('min_year (%s < %s)' % (entry['imdb_year'], config['min_year']))
            if 'reject_genres' in config:
                rejected = config['reject_genres']
                for genre in entry['imdb_genres']:
                    if genre in rejected:
                        reasons.append('reject_genres')
                        break
            if 'reject_languages' in config:
                rejected = config['reject_languages']
                for language in entry['imdb_languages']:
                    if language in rejected:
                        reasons.append('relect_languages')
                        break
            if 'accept_languages' in config:
                accepted = config['accept_languages']
                for language in entry['imdb_languages']:
                    if language not in accepted:
                        reasons.append('accept_languages')
                        break

            if reasons:
                msg = 'Skipping %s because of rule(s) %s' % (entry['title'], ', '.join(reasons))
                if feed.manager.options.debug:
                    log.debug(msg)
                else:
                    log_once(msg, log)
            else:
                log.debug('Accepting %s' % (entry))
                feed.accept(entry)


register_plugin(FilterImdb, 'imdb', priorities={'filter': 128})
