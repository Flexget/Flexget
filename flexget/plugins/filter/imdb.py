from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
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

      # accept movies with any of these genres
      accept_genres:
        - genre1
        - genre2

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

      # accept all movies by these writers
      accept_writers:
        - nm0000318

      # reject movies by these writers
      reject_writers:
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
            'accept': {'$ref': '#/definitions/imdb_rule_list'},
            'reject': {'$ref': '#/definitions/imdb_rule_list'},
            'accept_excluding': {'$ref': '#/definitions/imdb_rule_list'},
            'reject_excluding': {'$ref': '#/definitions/imdb_rule_list'},
            'rest': {'type': 'string', 'enum': ['accept', 'reject']},
        },
        'additionalProperties': False,
        'definitions': {
            'imdb_rule_list': {
                'type': 'array',
                'items': {
                    'min_year': {'type': 'integer'},
                    'max_year': {'type': 'integer'},
                    'min_votes': {'type': 'integer'},
                    'min_score': {'type': 'number'},
                    'genres': {'type': 'array', 'items': {'type': 'string'}},
                    'languages': {'type': 'array', 'items': {'type': 'string'}},
                    'actors': {'type': 'array', 'items': {'type': 'string'}},
                    'directors': {'type': 'array', 'items': {'type': 'string'}},
                    'writers': {'type': 'array', 'items': {'type': 'string'}},
                    'mpaa_ratings': {'type': 'array', 'items': {'type': 'string'}}
                }
            }
        }
    }

    # Run later to avoid unnecessary lookups
    @plugin.priority(120)
    def on_task_filter(self, task, config):
        rest = []
        for operation, imdb_rules in config.items():
            if operation == 'rest':
                continue
            leftovers = self.filter(task, operation, imdb_rules)
            if not rest:
                rest = leftovers
            else:
                # If there is already something in rest, take the intersection with r (entries no operations matched)
                rest = [entry for entry in leftovers if entry in rest]

        if 'rest' in config:
            rest_method = Entry.accept if config['rest'] == 'accept' else Entry.reject
            for entry in rest:
                log.debug('Rest method %s for %s' % (config['rest'], entry['title']))
                rest_method(entry, 'regexp `rest`')

    def filter(self, task, operation, imdb_rules):
        """
        :param task: Task instance
        :param operation: one of 'accept' 'reject' 'accept_excluding' and 'reject_excluding'
                          accept and reject will be called on the entry if any of the imdb_rules match
                          *_excluding operations will be called if any of the imdb_rules don't match
        :param imdb_rules: array of imdb_rules
        :return: Return list of entries that didn't match regexps
        """
        lookup = plugin.get_plugin_by_name('imdb_lookup').instance.lookup

        rest = []
        method = Entry.accept if 'accept' in operation else Entry.reject
        match_mode = 'excluding' not in operation

        for entry in task.entries:
            try:
                lookup(entry)
            except plugin.PluginError as e:
                # logs skip message once trough log_once (info) and then only when ran from cmd line (w/o --cron)
                msg = 'Skipping %s because of an error: %s' % (entry['title'], e.value)
                if not log_once(msg, logger=log):
                    log.verbose(msg)
                continue

            for rule in imdb_rules:
                rule_failed = False
                if 'min_score' in rule and entry.get('imdb_score', 0) < rule['min_score']:
                    rule_failed = True
                if 'max_score' in rule and entry.get('imdb_score', 0) > rule['max_score']:
                    rule_failed = True
                if 'min_votes' in rule and entry.get('imdb_votes', 0) < rule['min_votes']:
                    rule_failed = True
                if 'max_votes' in rule and entry.get('imdb_votes', 0) > rule['max_votes']:
                    rule_failed = True
                if 'min_year' in rule and entry.get('imdb_year', 0) < rule['min_year']:
                    rule_failed = True
                if 'max_year' in rule and entry.get('imdb_year', 0) > rule['max_year']:
                    rule_failed = True

                if 'genres' in rule:
                    genres = rule['genres']
                    for genre in entry.get('imdb_genres', []):
                        if genre in genres:
                            break
                    else:
                        rule_failed = True


                log.debug('rule_failed=%s' % rule_failed)


                if 'actors' in rule:
                    actors = rule['actors']
                    for actor_id, actor_name in entry.get('imdb_actors', {}).items():
                        if actor_id in actors or actor_name in actors:
                            break
                    else:
                        rule_failed = True


                if match_mode != rule_failed:
                    msg = 'Rule TODO %s ' % 'matched' if match_mode else 'didn\'t match'
                    if task.options.debug:
                        log.debug(msg)
                    else:
                        if task.options.cron:
                            log_once(msg, log)
                        else:
                            log.info(msg)
                    method(entry, msg)
                    break
            else:
                # We didn't run method for any of the rules, add this entry to rest
                entry.trace('None of configured %s rules matched' % operation)
                rest.append(entry)
        return rest





            #TODO
        def todo():
            if 'genres' in imdb_rules:
                accepted = imdb_rules['genres']
                accept_genre = False
                for genre in entry.get('imdb_genres', []):
                    if genre in imdb_rules['genres']:
                        method(entry, msg)
                        break
                if accept_genre == False:
                    reasons.append('accept_genres')

            if 'reject_genres' in imdb_rules:
                rejected = imdb_rules['reject_genres']
                for genre in entry.get('imdb_genres', []):
                    if genre in rejected:
                        reasons.append('reject_genres')
                        break

            if 'reject_languages' in imdb_rules:
                rejected = imdb_rules['reject_languages']
                for language in entry.get('imdb_languages', []):
                    if language in rejected:
                        reasons.append('reject_languages')
                        break

            if 'accept_languages' in imdb_rules:
                accepted = imdb_rules['accept_languages']
                if entry.get('imdb_languages') and entry['imdb_languages'][0] not in accepted:
                    # Reject if the first (primary) language is not among acceptable languages
                    reasons.append('accept_languages')

            if 'reject_actors' in imdb_rules:
                rejected = imdb_rules['reject_actors']
                for actor_id, actor_name in entry.get('imdb_actors', {}).items():
                    if actor_id in rejected or actor_name in rejected:
                        reasons.append('reject_actors %s' % actor_name or actor_id)
                        break

            # Accept if actors contains an accepted actor, but don't reject otherwise
            if 'accept_actors' in imdb_rules:
                accepted = imdb_rules['accept_actors']
                for actor_id, actor_name in entry.get('imdb_actors', {}).items():
                    if actor_id in accepted or actor_name in accepted:
                        log.debug('Accepting because of accept_actors %s' % actor_name or actor_id)
                        force_accept = True
                        break

            if 'reject_directors' in imdb_rules:
                rejected = imdb_rules['reject_directors']
                for director_id, director_name in entry.get('imdb_directors', {}).items():
                    if director_id in rejected or director_name in rejected:
                        reasons.append('reject_directors %s' % director_name or director_id)
                        break

            # Accept if the director is in the accept list, but do not reject if the director is unknown
            if 'accept_directors' in imdb_rules:
                accepted = imdb_rules['accept_directors']
                for director_id, director_name in entry.get('imdb_directors', {}).items():
                    if director_id in accepted or director_name in accepted:
                        log.debug('Accepting because of accept_directors %s' % director_name or director_id)
                        force_accept = True
                        break

            if 'reject_writers' in imdb_rules:
                rejected = imdb_rules['reject_writers']
                for writer_id, writer_name in entry.get('imdb_writers', {}).items():
                    if writer_id in rejected or writer_name in rejected:
                        reasons.append('reject_writers %s' % writer_name or writer_id)
                        break

            # Accept if the writer is in the accept list, but do not reject if the writer is unknown
            if 'accept_writers' in imdb_rules:
                accepted = imdb_rules['accept_writers']
                for writer_id, writer_name in entry.get('imdb_writers', {}).items():
                    if writer_id in accepted or writer_name in accepted:
                        log.debug('Accepting because of accept_writers %s' % writer_name or writer_id)
                        force_accept = True
                        break

            if 'reject_mpaa_ratings' in imdb_rules:
                rejected = imdb_rules['reject_mpaa_ratings']
                if entry.get('imdb_mpaa_rating') in rejected:
                    reasons.append('reject_mpaa_ratings %s' % entry['imdb_mpaa_rating'])

            if 'accept_mpaa_ratings' in imdb_rules:
                accepted = imdb_rules['accept_mpaa_ratings']
                if entry.get('imdb_mpaa_rating') not in accepted:
                    reasons.append('accept_mpaa_ratings %s' % entry.get('imdb_mpaa_rating'))

            if reasons and not force_accept:
                msg = 'Didn\'t accept `%s` because of rule(s) %s' % \
                      (entry.get('imdb_name', None) or entry['title'], ', '.join(reasons))
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
    plugin.register(FilterImdb, 'imdb', api_ver=2)
