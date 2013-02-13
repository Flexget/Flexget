from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, priority, get_plugin_by_name, PluginError
from flexget.utils.log import log_once

log = logging.getLogger('thetvdb')


class FilterTvdb(object):
    """
        This plugin allows filtering based on thetvdb series rating,
        episode rating, status, genres, runtime, content-rating,
        languages, directors, writers, network, guest stars, episode
        rating, and actors

        Configuration:

        Note: All parameters are optional. Some are mutually exclusive.

        min_series_rating: <num>
        min_episode_rating: <num>
        min_episode_air_year: <num>
        max_episode_air_year: <num>
        min_episode_runtime: <num>
        max_episode_runtime: <num>

        # reject if genre contains any of these
        reject_content_rating:
            - TV-MA
        # accept only this content rating
        accept_content_rating:
            - TV-PG

        # accept only these networks
        accept_network:
            - NBC
        # reject if this network
        reject_network:
            - ABC

        # reject if genre contains any of these
        reject_genres:
            - drama
            - romance

        # reject if status contains any of these
        reject_status:
            - Ended

        # reject if language contain any of these
        reject_languages:
            - fr
        # accept only this language
        accept_languages:
            - en

        # Actors below take into account series actors, and guest stars
        # accept episode with any of these actors
        accept_actors:
            - Heidi Klum
            - Bruce Willis
        # reject episode if it has any of these actors
        reject_actors:
            - Cher
            - Tamala Jones

        # accept all episodes by these writers
        accept_writers:
            - Andrew W. Marlowe
        # reject episodes by these writers
        reject_writers:
            - Barry Schindel

        # accept all episodes by these directors
        accept_directors:
            - Rob Bowman
        # reject movies by these directors
        reject_directors:
            - John Terlesky
    """

    def validator(self):
        """Validate given configuration"""
        from flexget import validator
        thetvdb = validator.factory('dict')
        thetvdb.accept('number', key='min_series_rating')
        thetvdb.accept('number', key='min_episode_rating')
        thetvdb.accept('integer', key='min_episode_air_year')
        thetvdb.accept('integer', key='max_episode_air_year')
        thetvdb.accept('number', key='min_episode_runtime')
        thetvdb.accept('number', key='max_episode_runtime')
        thetvdb.accept('list', key='reject_content_rating').accept('text')
        thetvdb.accept('list', key='accept_content_rating').accept('text')
        thetvdb.accept('list', key='accept_network').accept('text')
        thetvdb.accept('list', key='reject_network').accept('text')
        thetvdb.accept('list', key='reject_genres').accept('text')
        thetvdb.accept('list', key='reject_status').accept('text')
        thetvdb.accept('list', key='reject_languages').accept('text')
        thetvdb.accept('list', key='accept_languages').accept('text')
        thetvdb.accept('list', key='accept_actors').accept('text')
        thetvdb.accept('list', key='reject_actors').accept('text')
        thetvdb.accept('list', key='accept_writers').accept('text')
        thetvdb.accept('list', key='reject_writers').accept('text')
        thetvdb.accept('list', key='accept_directors').accept('text')
        thetvdb.accept('list', key='reject_directors').accept('text')
        return thetvdb

    def is_in_set(self, config, configkey, entryitem,):
        '''
        this takes the config object, config key (to a list), and entry
        item so it can return True if the object matches,
        (be that a subset of the list, or if the entry item is contained
        within the config object list) or false if it does not.
        '''
        # will want to port this over to filter_imdb as well, for code
        # clarity in that module.
        if configkey in config:
            configlist = config[configkey]
            if isinstance(entryitem, list):
                for item in entryitem:
                    if item in configlist:
                        return True
            else:
                if entryitem in configlist:
                    return True
        return False

    @priority(126)
    def on_task_filter(self, task):
        config = task.config['thetvdb']

        lookup = get_plugin_by_name('thetvdb_lookup').instance.lookup

        for entry in task.entries:
            force_accept = False

            try:
                lookup(task, entry)
            except PluginError as e:
                log.error('Skipping %s because of an error: %s' % (entry['title'], e.value))
                continue

            # Check defined conditions
            reasons = []
            if 'min_series_rating' in config:
                if entry['tvdb_rating'] < config['min_series_rating']:
                    reasons.append('series_rating (%s < %s)' % (entry['tvdb_rating'], config['min_series_rating']))
            if 'min_episode_rating' in config:
                if entry['tvdb_ep_rating'] < config['min_episode_rating']:
                    reasons.append('tvdb_ep_rating (%s < %s)' % (entry['tvdb_ep_rating'], config['min_episode_rating']))
            if 'min_episode_air_year' in config:
                if entry['tvdb_ep_air_date'].strftime("%Y") < config['min_episode_air_year']:
                    reasons.append('tvdb_ep_air_date (%s < %s)' % (entry['tvdb_ep_air_date'].strftime("%Y"), config['min_episode_air_year']))
            if 'max_episode_air_year' in config:
                if entry['tvdb_ep_air_date'].strftime("%Y") > config['max_episode_air_year']:
                    reasons.append('tvdb_ep_air_date (%s < %s)' % (entry['tvdb_ep_air_date'].strftime("%Y"), config['max_episode_air_year']))

            if self.is_in_set(config, 'reject_content_rating', entry['tvdb_content_rating']):
                reasons.append('reject_content_rating')

            if not self.is_in_set(config, 'accept_content_rating', entry['tvdb_content_rating']):
                reasons.append('accept_content_rating')

            if self.is_in_set(config, 'reject_network', entry['tvdb_network']):
                reasons.append('reject_network')

            if not self.is_in_set(config, 'accept_network', entry['tvdb_network']):
                reasons.append('accept_network')

            if self.is_in_set(config, 'reject_genres', entry['tvdb_genres']):
                reasons.append('reject_genres')

            if self.is_in_set(config, 'reject_status', entry['tvdb_status']):
                reasons.append('reject_status')

            if self.is_in_set(config, 'reject_languages', entry['tvdb_language']):
                reasons.append('reject_languages')

            if not self.is_in_set(config, 'accept_languages', entry['tvdb_language']):
                reasons.append('accept_languages')

            # Accept if actors contains an accepted actor, but don't reject otherwise
            if self.is_in_set(config, 'accept_actors', entry['tvdb_actors'] + entry['tvdb_ep_guest_stars']):
                force_accept = True

            if self.is_in_set(config, 'reject_actors', entry['tvdb_actors'] + entry['tvdb_ep_guest_stars']):
                reasons.append('reject_genres')

            # Accept if writer is an accepted writer, but don't reject otherwise
            if self.is_in_set(config, 'accept_writers', entry['tvdb_ep_writer']):
                force_accept = True

            if self.is_in_set(config, 'reject_writers', entry['tvdb_ep_writer']):
                reasons.append('reject_writers')

            # Accept if director is an accepted director, but don't reject otherwise
            if self.is_in_set(config, 'accept_directors', entry['tvdb_ep_director']):
                force_accept = True

            if self.is_in_set(config, 'reject_directors', entry['tvdb_ep_director']):
                reasons.append('reject_directors')

            if reasons and not force_accept:
                msg = 'Skipping %s because of rule(s) %s' % \
                    (entry.get('series_name_thetvdb', None) or entry['title'], ', '.join(reasons))
                if task.manager.options.debug:
                    log.debug(msg)
                else:
                    log_once(msg, log)
            else:
                log.debug('Accepting %s' % (entry))
                entry.accept()

register_plugin(FilterTvdb, 'thetvdb')
