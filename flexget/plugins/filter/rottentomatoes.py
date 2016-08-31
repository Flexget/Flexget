from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.log import log_once

log = logging.getLogger('rt')


class FilterRottenTomatoes(object):
    """
        This plugin allows filtering based on Rotten Tomatoes score, votes and genres etc.

        Configuration:

        Note: All parameters are optional. Some are mutually exclusive.

        min_critics_score: <num>
        min_audience_score: <num>
        min_average_score: <num>
        min_critics_rating: <rotten, fresh, or certified fresh>
        min_audience_rating: <upright or spilled>
        min_year: <num>
        max_year: <num>

        # reject if genre contains any of these
        reject_genres:
            - genre1
            - genre2

        # accept movies with any of these actors
        accept_actors:
            - actor1
            - actor2

        # reject movie if it has any of these actors
        reject_actors:
            - actor3
            - actor4

        # accept all movies by these directors
        accept_directors:
            - director1

        # reject movies by these directors
        reject_directors:
            - director2

        # reject movies with any of these ratings
        reject_mpaa_ratings:
            - PG-13
            - R
            - X

        # accept movies with only these ratings
        accept_mpaa_ratings:
            - PG
            - G
    """

    def __init__(self):
        # We could pull these from the API through lists.json but that's extra web/API key usage
        self.critics_ratings = {'rotten': 0, 'fresh': 1, 'certified fresh': 2}
        self.audience_ratings = {'spilled': 0, 'upright': 1}

    def validator(self):
        from flexget import validator
        rt = validator.factory('dict')
        rt.accept('integer', key='min_year')
        rt.accept('integer', key='max_year')
        rt.accept('number', key='min_critics_score')
        rt.accept('number', key='min_audience_score')
        rt.accept('number', key='min_average_score')
        rt.accept('choice', key='min_critics_rating').accept_choices(list(self.critics_ratings.keys()))
        rt.accept('choice', key='min_audience_rating').accept_choices(list(self.audience_ratings.keys()))
        rt.accept('list', key='reject_genres').accept('text')
        rt.accept('list', key='reject_actors').accept('text')
        rt.accept('list', key='accept_actors').accept('text')
        rt.accept('list', key='reject_directors').accept('text')
        rt.accept('list', key='accept_directors').accept('text')
        rt.accept('list', key='reject_mpaa_ratings').accept('text')
        rt.accept('list', key='accept_mpaa_ratings').accept('text')
        return rt

    # Run later to avoid unnecessary lookups
    @plugin.priority(115)
    def on_task_filter(self, task, config):

        lookup = plugin.get_plugin_by_name('rottentomatoes_lookup').instance.lookup

        # since the plugin does not reject anything, no sense going trough accepted
        for entry in task.undecided:

            force_accept = False

            try:
                lookup(entry)
            except plugin.PluginError as e:
                # logs skip message once through log_once (info) and then only when ran from cmd line (w/o --cron)
                msg = 'Skipping %s because of an error: %s' % (entry['title'], e.value)
                if not log_once(msg, logger=log):
                    log.verbose(msg)
                continue

            # for key, value in entry.iteritems():
            #     log.debug('%s = %s (type: %s)' % (key, value, type(value)))

            # Check defined conditions, TODO: rewrite into functions?
            reasons = []
            if 'min_critics_score' in config:
                if entry.get('rt_critics_score', 0) < config['min_critics_score']:
                    reasons.append('min_critics_score (%s < %s)' % (entry.get('rt_critics_score'),
                                                                    config['min_critics_score']))
            if 'min_audience_score' in config:
                if entry.get('rt_audience_score', 0) < config['min_audience_score']:
                    reasons.append('min_audience_score (%s < %s)' % (entry.get('rt_audience_score'),
                                                                     config['min_audience_score']))
            if 'min_average_score' in config:
                if entry.get('rt_average_score', 0) < config['min_average_score']:
                    reasons.append('min_average_score (%s < %s)' % (entry.get('rt_average_score'),
                                                                    config['min_average_score']))
            if 'min_critics_rating' in config:
                if not entry.get('rt_critics_rating'):
                    reasons.append('min_critics_rating (no rt_critics_rating)')
                elif self.critics_ratings.get(entry.get('rt_critics_rating').lower(),
                                              0) < self.critics_ratings[config['min_critics_rating']]:
                    reasons.append('min_critics_rating (%s < %s)' % (entry.get('rt_critics_rating').lower(),
                                                                     config['min_critics_rating']))
            if 'min_audience_rating' in config:
                if not entry.get('rt_audience_rating'):
                    reasons.append('min_audience_rating (no rt_audience_rating)')
                elif self.audience_ratings.get(entry.get('rt_audience_rating').lower(),
                                               0) < self.audience_ratings[config['min_audience_rating']]:
                    reasons.append('min_audience_rating (%s < %s)' % (entry.get('rt_audience_rating').lower(),
                                                                      config['min_audience_rating']))
            if 'min_year' in config:
                if entry.get('rt_year', 0) < config['min_year']:
                    reasons.append('min_year (%s < %s)' % (entry.get('rt_year'), config['min_year']))
            if 'max_year' in config:
                if entry.get('rt_year', 0) > config['max_year']:
                    reasons.append('max_year (%s > %s)' % (entry.get('rt_year'), config['max_year']))
            if 'reject_genres' in config:
                rejected = config['reject_genres']
                for genre in entry.get('rt_genres', []):
                    if genre in rejected:
                        reasons.append('reject_genres')
                        break

            if 'reject_actors' in config:
                rejected = config['reject_actors']
                for actor_name in entry.get('rt_actors', []):
                    if actor_name in rejected:
                        reasons.append('reject_actors %s' % actor_name)
                        break

            # Accept if actors contains an accepted actor, but don't reject otherwise
            if 'accept_actors' in config:
                accepted = config['accept_actors']
                for actor_name in entry.get('rt_actors', []):
                    if actor_name in accepted:
                        log.debug('Accepting because of accept_actors %s' % actor_name)
                        force_accept = True
                        break

            if 'reject_directors' in config:
                rejected = config['reject_directors']
                for director_name in entry.get('rt_directors', []):
                    if director_name in rejected:
                        reasons.append('reject_directors %s' % director_name)
                        break

            # Accept if the director is in the accept list, but do not reject if the director is unknown
            if 'accept_directors' in config:
                accepted = config['accept_directors']
                for director_name in entry.get('rt_directors', []):
                    if director_name in accepted:
                        log.debug('Accepting because of accept_directors %s' % director_name)
                        force_accept = True
                        break

            if 'reject_mpaa_ratings' in config:
                rejected = config['reject_mpaa_ratings']
                if entry.get('rt_mpaa_rating') in rejected:
                    reasons.append('reject_mpaa_ratings %s' % entry['rt_mpaa_rating'])

            if 'accept_mpaa_ratings' in config:
                accepted = config['accept_mpaa_ratings']
                if entry.get('rt_mpaa_rating') not in accepted:
                    reasons.append('accept_mpaa_ratings %s' % entry.get('rt_mpaa_rating'))

            if reasons and not force_accept:
                msg = 'Didn\'t accept `%s` because of rule(s) %s' % \
                      (entry.get('rt_name', None) or entry['title'], ', '.join(reasons))
                if task.options.debug:
                    log.debug(msg)
                else:
                    if task.options.cron:
                        log_once(msg, log)
                    else:
                        log.info(msg)
            else:
                log.debug('Accepting %s' % (entry['title']))
                entry.accept()


@event('plugin.register')
def register_plugin():
    plugin.register(FilterRottenTomatoes, 'rottentomatoes', api_ver=2)
