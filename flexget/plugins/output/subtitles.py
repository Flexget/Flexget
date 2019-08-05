from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.xmlrpc.client import ServerProxy

import re
import difflib
import os.path
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('subtitles')

# movie hash, won't work here though
# http://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes#Python

# xmlrpc spec
# http://trac.opensubtitles.org/projects/opensubtitles/wiki/XMLRPC


class Subtitles(object):
    """
    Fetch subtitles from opensubtitles.org
    """

    schema = {
        'type': 'object',
        'properties': {
            'languages': {'type': 'array', 'items': {'type': 'string'}, 'default': ['eng']},
            'min_sub_rating': {'type': 'number', 'default': 0.0},
            'match_limit': {'type': 'number', 'default': 0.8},
            'output': {'type': 'string', 'format': 'path'},
        },
        'additionalProperties': False,
    }

    def prepare_config(self, config, task):
        if not isinstance(config, dict):
            config = {}
        config.setdefault('output', task.manager.config_base)
        config['output'] = os.path.expanduser(config['output'])
        return config

    def on_task_download(self, task, config):

        # filter all entries that have IMDB ID set
        try:
            entries = [e for e in task.accepted if e['imdb_id'] is not None]
        except KeyError:
            # No imdb urls on this task, skip it
            # TODO: should do lookup via imdb_lookup plugin?
            return

        try:
            s = ServerProxy("http://api.opensubtitles.org/xml-rpc")
            res = s.LogIn("", "", "en", "FlexGet")
        except Exception:
            log.warning('Error connecting to opensubtitles.org')
            return

        if res['status'] != '200 OK':
            raise Exception("Login to opensubtitles.org XML-RPC interface failed")

        config = self.prepare_config(config, task)

        token = res['token']

        # configuration
        languages = config['languages']
        min_sub_rating = config['min_sub_rating']
        match_limit = config[
            'match_limit'
        ]  # no need to change this, but it should be configurable

        # loop through the entries
        for entry in entries:
            imdbid = entry.get('imdb_id')
            if not imdbid:
                log.debug('no match for %s' % entry['title'])
                continue

            query = []
            for language in languages:
                query.append({'sublanguageid': language, 'imdbid': imdbid})

            subtitles = s.SearchSubtitles(token, query)
            subtitles = subtitles['data']

            # nothing found -> continue
            if not subtitles:
                continue

            # filter bad subs
            subtitles = [x for x in subtitles if x['SubBad'] == '0']
            # some quality required (0.0 == not reviewed)
            subtitles = [
                x
                for x in subtitles
                if float(x['SubRating']) >= min_sub_rating or float(x['SubRating']) == 0.0
            ]

            filtered_subs = []

            # find the best rated subs for each language
            for language in languages:
                langsubs = [x for x in subtitles if x['SubLanguageID'] == language]

                # did we find any subs for this language?
                if langsubs:

                    def seqmatch(subfile):
                        s = difflib.SequenceMatcher(lambda x: x in " ._", entry['title'], subfile)
                        # print "matching: ", entry['title'], subfile, s.ratio()
                        return s.ratio() > match_limit

                    # filter only those that have matching release names
                    langsubs = [x for x in subtitles if seqmatch(x['MovieReleaseName'])]

                    if langsubs:
                        # find the best one by SubRating
                        langsubs.sort(key=lambda x: float(x['SubRating']))
                        langsubs.reverse()
                        filtered_subs.append(langsubs[0])

            # download
            for sub in filtered_subs:
                log.debug(
                    'SUBS FOUND: %s %s %s'
                    % (sub['MovieReleaseName'], sub['SubRating'], sub['SubLanguageID'])
                )

                f = task.requests.get(sub['ZipDownloadLink'])
                subfilename = re.match(
                    '^attachment; filename="(.*)"$', f.headers['content-disposition']
                ).group(1)
                outfile = os.path.join(config['output'], subfilename)
                fp = open(outfile, 'w')
                fp.write(f.raw)
                fp.close()
                f.close()

        s.LogOut(token)


@event('plugin.register')
def register_plugin():
    plugin.register(Subtitles, 'subtitles', api_ver=2)
