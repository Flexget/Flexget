from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.log import log_once

logger = logger.bind(name='imdb')


class FilterImdb:
    """
    This plugin allows filtering based on IMDB score, votes and genres etc.

    Note: All parameters are optional. Some are mutually exclusive.

    Configuration::

      min_score: <num>
      min_votes: <num>
      min_meta_score: <num>
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
            'min_year': {'type': 'integer'},
            'max_year': {'type': 'integer'},
            'min_votes': {'type': 'integer'},
            'min_meta_score': {'type': 'integer'},
            'min_score': {'type': 'number'},
            'accept_genres': {'type': 'array', 'items': {'type': 'string'}},
            'reject_genres': {'type': 'array', 'items': {'type': 'string'}},
            'reject_languages': {'type': 'array', 'items': {'type': 'string'}},
            'accept_languages': {'type': 'array', 'items': {'type': 'string'}},
            'reject_actors': {'type': 'array', 'items': {'type': 'string'}},
            'accept_actors': {'type': 'array', 'items': {'type': 'string'}},
            'reject_directors': {'type': 'array', 'items': {'type': 'string'}},
            'accept_directors': {'type': 'array', 'items': {'type': 'string'}},
            'reject_writers': {'type': 'array', 'items': {'type': 'string'}},
            'accept_writers': {'type': 'array', 'items': {'type': 'string'}},
            'reject_mpaa_ratings': {'type': 'array', 'items': {'type': 'string'}},
            'accept_mpaa_ratings': {'type': 'array', 'items': {'type': 'string'}},
        },
        'additionalProperties': False,
    }

    # Run later to avoid unnecessary lookups
    @plugin.priority(120)
    def on_task_filter(self, task, config):

        lookup = plugin.get('imdb_lookup', self).lookup

        # since the plugin does not reject anything, no sense going trough accepted
        for entry in task.undecided:

            force_accept = False

            try:
                lookup(entry)
            except plugin.PluginError as e:
                # logs skip message once trough log_once (info) and then only when ran from cmd line (w/o --cron)
                log_once(
                    'Skipping %s because of an error: %s' % (entry['title'], e.value),
                    logger=logger,
                )
                continue

            # for key, value in entry.iteritems():
            #     log.debug('%s = %s (type: %s)' % (key, value, type(value)))

            # Check defined conditions, TODO: rewrite into functions?
            reasons = []
            if 'min_score' in config:
                if entry.get('imdb_score', 0) < config['min_score']:
                    reasons.append(
                        'min_score (%s < %s)' % (entry.get('imdb_score'), config['min_score'])
                    )
            if 'min_votes' in config:
                if entry.get('imdb_votes', 0) < config['min_votes']:
                    reasons.append(
                        'min_votes (%s < %s)' % (entry.get('imdb_votes'), config['min_votes'])
                    )
            if 'min_meta_score' in config:
                if entry.get('imdb_meta_score', 0) < config['min_meta_score']:
                    reasons.append(
                        'min_meta_score (%s < %s)'
                        % (entry.get('imdb_meta_score'), config['min_meta_score'])
                    )
            if 'min_year' in config:
                if entry.get('imdb_year', 0) < config['min_year']:
                    reasons.append(
                        'min_year (%s < %s)' % (entry.get('imdb_year'), config['min_year'])
                    )
            if 'max_year' in config:
                if entry.get('imdb_year', 0) > config['max_year']:
                    reasons.append(
                        'max_year (%s > %s)' % (entry.get('imdb_year'), config['max_year'])
                    )

            if 'accept_genres' in config:
                accepted = config['accept_genres']
                accept_genre = False
                for genre in entry.get('imdb_genres', []):
                    if genre in accepted:
                        accept_genre = True
                        break
                if accept_genre == False:
                    reasons.append('accept_genres')

            if 'reject_genres' in config:
                rejected = config['reject_genres']
                for genre in entry.get('imdb_genres', []):
                    if genre in rejected:
                        reasons.append('reject_genres')
                        break

            if 'reject_languages' in config:
                rejected = config['reject_languages']
                for language in entry.get('imdb_languages', []):
                    if language in rejected:
                        reasons.append('reject_languages')
                        break

            if 'accept_languages' in config:
                accepted = config['accept_languages']
                if entry.get('imdb_languages') and entry['imdb_languages'][0] not in accepted:
                    # Reject if the first (primary) language is not among acceptable languages
                    reasons.append('accept_languages')

            if 'reject_actors' in config:
                rejected = config['reject_actors']
                for actor_id, actor_name in entry.get('imdb_actors', {}).items():
                    if actor_id in rejected or actor_name in rejected:
                        reasons.append('reject_actors %s' % actor_name or actor_id)
                        break

            # Accept if actors contains an accepted actor, but don't reject otherwise
            if 'accept_actors' in config:
                accepted = config['accept_actors']
                for actor_id, actor_name in entry.get('imdb_actors', {}).items():
                    if actor_id in accepted or actor_name in accepted:
                        logger.debug(
                            'Accepting because of accept_actors {}', actor_name or actor_id
                        )
                        force_accept = True
                        break

            if 'reject_directors' in config:
                rejected = config['reject_directors']
                for director_id, director_name in entry.get('imdb_directors', {}).items():
                    if director_id in rejected or director_name in rejected:
                        reasons.append('reject_directors %s' % director_name or director_id)
                        break

            # Accept if the director is in the accept list, but do not reject if the director is unknown
            if 'accept_directors' in config:
                accepted = config['accept_directors']
                for director_id, director_name in entry.get('imdb_directors', {}).items():
                    if director_id in accepted or director_name in accepted:
                        logger.debug(
                            'Accepting because of accept_directors {}',
                            director_name or director_id,
                        )
                        force_accept = True
                        break

            if 'reject_writers' in config:
                rejected = config['reject_writers']
                for writer_id, writer_name in entry.get('imdb_writers', {}).items():
                    if writer_id in rejected or writer_name in rejected:
                        reasons.append('reject_writers %s' % writer_name or writer_id)
                        break

            # Accept if the writer is in the accept list, but do not reject if the writer is unknown
            if 'accept_writers' in config:
                accepted = config['accept_writers']
                for writer_id, writer_name in entry.get('imdb_writers', {}).items():
                    if writer_id in accepted or writer_name in accepted:
                        logger.debug(
                            'Accepting because of accept_writers {}', writer_name or writer_id
                        )
                        force_accept = True
                        break

            if 'reject_mpaa_ratings' in config:
                rejected = config['reject_mpaa_ratings']
                if entry.get('imdb_mpaa_rating') in rejected:
                    reasons.append('reject_mpaa_ratings %s' % entry['imdb_mpaa_rating'])

            if 'accept_mpaa_ratings' in config:
                accepted = config['accept_mpaa_ratings']
                if entry.get('imdb_mpaa_rating') not in accepted:
                    reasons.append('accept_mpaa_ratings %s' % entry.get('imdb_mpaa_rating'))

            if reasons and not force_accept:
                msg = 'Didn\'t accept `%s` because of rule(s) %s' % (
                    entry.get('imdb_name', None) or entry['title'],
                    ', '.join(reasons),
                )
                if task.options.debug:
                    logger.debug(msg)
                else:
                    if task.options.cron:
                        log_once(msg, logger)
                    else:
                        logger.info(msg)
            else:
                logger.debug('Accepting {}', entry['title'])
                entry.accept()


@event('plugin.register')
def register_plugin():
    plugin.register(FilterImdb, 'imdb', api_ver=2)
