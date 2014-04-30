from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.log import log_once

log = logging.getLogger('imdb')


class FilterImdb(object):
    """
    This plugin allows filtering based on IMDB score, votes and genres etc.

    Note: All parameters are optional. Some are mutually exclusive.

    Configuration::

      min_score: <num>
      min_votes: <num>
      min_year: <num>
      max_year: <num>

      # reject if genre contains any of these
      reject_genres:
        - genre1
        - genre2

      # reject if language contain any of these
      reject_languages:
        - language1

      # accept only these primary languages
      accept_languages:
        - language1

      # accept movies with any of these actors
      accept_actors:
        - nm0004695
        - nm0004754

      # reject movie if it has any of these actors
      reject_actors:
        - nm0001191
        - nm0002071

      # accept all movies by these directors
      accept_directors:
        - nm0000318

      # reject movies by these directors
      reject_directors:
        - nm0093051

      # reject movies/TV shows with any of these ratings
      reject_mpaa_ratings:
        - PG_13
        - R
        - X

      # accept movies/TV shows with only these ratings
      accept_mpaa_ratings:
        - PG
        - G
        - TV_Y
    """

    schema = {
        'type': 'object',
        'properties': {
            'min_year': {'type': 'integer'},
            'max_year': {'type': 'integer'},
            'min_votes': {'type': 'integer'},
            'min_score': {'type': 'number'},
            'reject_genres': {'type': 'array', 'items': {'type': 'string'}},
            'reject_languages': {'type': 'array', 'items': {'type': 'string'}},
            'accept_languages': {'type': 'array', 'items': {'type': 'string'}},
            'reject_actors': {'type': 'array', 'items': {'type': 'string'}},
            'accept_actors': {'type': 'array', 'items': {'type': 'string'}},
            'reject_directors': {'type': 'array', 'items': {'type': 'string'}},
            'accept_directors': {'type': 'array', 'items': {'type': 'string'}},
            'reject_mpaa_ratings': {'type': 'array', 'items': {'type': 'string'}},
            'accept_mpaa_ratings': {'type': 'array', 'items': {'type': 'string'}}
        },
        'additionalProperties': False
    }

    # Run later to avoid unnecessary lookups
    @plugin.priority(120)
    def on_task_filter(self, task, config):
        lookup = plugin.get_plugin_by_name('imdb_lookup').instance.lookup

        for entry in task.entries:
            try:
                lookup(entry)
            except plugin.PluginError as e:
                # logs skip message once trough log_once (info) and then only when ran from cmd line (w/o --cron)
                msg = 'Skipping %s because of an error: %s' % (entry['title'], e.value)
                if not log_once(msg, logger=log):
                    log.verbose(msg)
                continue

            #for key, value in entry.iteritems():
            #    log.debug('%s = %s (type: %s)' % (key, value, type(value)))

            # Check defined conditions, TODO: rewrite into functions?
            reject_reasons = []
            accept_reasons = []
            
            if 'min_score' in config:
                if entry.get('imdb_score', 0) < config['min_score']:
                    reject_reasons.append('min_score (%s < %s)' % (entry.get('imdb_score'), config['min_score']))
            
            if 'min_votes' in config:
                if entry.get('imdb_votes', 0) < config['min_votes']:
                    reject_reasons.append('min_votes (%s < %s)' % (entry.get('imdb_votes'), config['min_votes']))
            
            if 'min_year' in config:
                if entry.get('imdb_year', 0) < config['min_year']:
                    reject_reasons.append('min_year (%s < %s)' % (entry.get('imdb_year'), config['min_year']))
            
            if 'max_year' in config:
                if entry.get('imdb_year', 0) > config['max_year']:
                    reject_reasons.append('max_year (%s > %s)' % (entry.get('imdb_year'), config['max_year']))
            
            if 'reject_genres' in config:
                rejected = config['reject_genres']
                for genre in entry.get('imdb_genres', []):
                    if genre in rejected:
                        reject_reasons.append('reject_genres %s' % genre)
                        break

            if 'reject_languages' in config:
                rejected = config['reject_languages']
                for language in entry.get('imdb_languages', []):
                    if language in rejected:
                        reject_reasons.append('reject_languages %s' % language)
                        break

            if 'accept_languages' in config:
                accepted = config['accept_languages']
                for language in entry.get('imdb_languages', []):
                    if language in accepted:
                        accept_reasons.append('reject_languages %s' % language)
                        break

            if 'reject_actors' in config:
                rejected = config['reject_actors']
                for actor_id, actor_name in entry.get('imdb_actors', {}).iteritems():
                    if actor_id in rejected or actor_name in rejected:
                        reject_reasons.append('reject_actors %s' % actor_name or actor_id)
                        break

            if 'accept_actors' in config:
                accepted = config['accept_actors']
                for actor_id, actor_name in entry.get('imdb_actors', {}).iteritems():
                    if actor_id in accepted or actor_name in accepted:
                        accept_reasons.append('accept_actors %s' % actor_name or actor_id)
                        break

            if 'reject_directors' in config:
                rejected = config['reject_directors']
                for director_id, director_name in entry.get('imdb_directors', {}).iteritems():
                    if director_id in rejected or director_name in rejected:
                        reject_reasons.append('reject_directors %s' % director_name or director_id)
                        break

            if 'accept_directors' in config:
                accepted = config['accept_directors']
                for director_id, director_name in entry.get('imdb_directors', {}).iteritems():
                    if director_id in accepted or director_name in accepted:
                        accept_reasons.append('accept_directors %s' % director_name or director_id)
                        break

            if 'reject_mpaa_ratings' in config:
                rejected = config['reject_mpaa_ratings']
                if entry.get('imdb_mpaa_rating') in rejected:
                    reject_reasons.append('reject_mpaa_ratings %s' % entry['imdb_mpaa_rating'])

            if 'accept_mpaa_ratings' in config:
                accepted = config['accept_mpaa_ratings']
                if entry.get('imdb_mpaa_rating') in accepted:
                    accept_reasons.append('accept_mpaa_ratings %s' % entry['imdb_mpaa_rating'])

            if reject_reasons:
                entry.reject(', '.join(reject_reasons))
            elif accept_reasons:
                entry.accept(', '.join(accept_reasons))
            else:
                log.debug('Found no reason to accept or reject %s' % entry['title'])

@event('plugin.register')
def register_plugin():
    plugin.register(FilterImdb, 'imdb', api_ver=2)
