from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import os
import xml.etree.ElementTree as ET

from flexget import plugin
from flexget.event import event
from flexget.plugins.metainfo.imdb_lookup import ImdbLookup

log = logging.getLogger('nfo_lookup')


class NfoLookup(object):
    """
    Retrieves information from a local '.nfo' info file.

    The read metadata will be add as 'nfo_something' in the entry. Also, if an
    'id' is found in the '.nfo' file then the 'imdb_id' field will be set to
    its value. This means that if the imdb_lookup plugin is used in addition to
    this plugin it will be able to use the ID from '.nfo' file to get the
    correct movie.

    The nfo file is used by Kodi.

    Example:
        nfo_lookup: yes

    WARNING: This plugin will read a file with extension '.nfo' and the same
    name as the entry filename as an XML file using xml.etree.ElementTree from
    the standard python library. As such, it is vulnerable to XML
    vulnerabilities described in the link below
    https://docs.python.org/3/library/xml.html#xml-vulnerabilities

    Use this only with nfo files you have created yourself.
    """
    schema = {'type': 'boolean'}

    # TODO: Maybe refactor this to allow an option specifying a different extension
    nfo_file_extension = '.nfo'

    def on_task_metainfo(self, task, config):
        # check if disabled (value set to false)
        if not config:
            # Config was set to 'no' instead of yes. Don't do anything then.
            return

        for entry in task.entries:
            # If this entry was obtained from the filesystem plugin it should
            # have a filename field. If it does not have one then there is
            # nothing we can do in this plugin.
            filename = entry.get('filename')
            location = entry.get('location')

            # If there is no 'filename' field there is also no nfo file
            if filename is None or location is None:
                log.warning("Entry '{0}' didn't come from the filesystem plugin".format(entry.get('title')))
                nfo_filename = None
            else:
                # This will be None if there is no nfo file
                nfo_filename = self.get_nfo_filename(entry)
                # Stop if there is no nfo file
                if nfo_filename is None:
                    log.warning(
                        "Entry '{0}' has no corresponding '{1}' file".format(
                            entry.get('title'), self.nfo_file_extension))
                    return

            # Populate the fields from the information in the .nfo file
            self.lookup(entry, nfo_filename)

    def lookup(self, entry, nfo_filename):
        # If there is already data from a previous parse then we don't need to
        # do anything
        if entry.get('nfo_id') is not None:
            log.warning("Entry '{0}' was already parsed by nfo_lookup. "
                        "I won't do anything.".format(entry.get('title')))
            return

        # In case there is no nfo file, `nfo_filename` will be None at this point
        if nfo_filename is None:
            # Setting the fields dictionary to be an empty dictionary here
            # means that no new information will be added to the entry in this
            # lookup function. We will still perform an IMDB lookup later, but
            # it will be the same as if we had used the imdb_lookup plugin.
            fields = {}
        else:
            # Get all values we can from the nfo file
            fields = NfoReader.get_fields_from_nfo_file(nfo_filename)

            # Update the entry with the just the imdb_id. This will help the
            # imdb_lookup plugin to get the correct data if it is also used
            if 'nfo_id' in fields:
                entry.update({u'imdb_id': fields['nfo_id']})

        entry.update(fields)

    # TODO: Remove this method
    def add_imdb_fields_to_dict(self, fields):
        """
        Take the dictionary of 'nfo fields' and add extra keys with 'imdb fields'
        corresponding to the 'nfo fields'
        """
        single_field_mapping = {
            # u'nfo_id': u'imdb_id',
            u'nfo_title': u'imdb_name',
            u'nfo_originaltitle': u'imdb_original_name',
            # u'nfo_votes' u'imdb_votes',
            # u'nfo_year': u'imdb_year',
            u'nfo_plot': u'imdb_plot_outline',
            # u'nfo_rating': u'imdb_score',
            # u'nfo_thumb': u'imdb_photo'
        }

        # multiple_field_mapping = {
        #     # List of imdb genres
        #     u'nfo_genre': u'imdb_genres',
        #     # Directors dictionary (imdbid, name)
        #     u'nfo_director': u'imdb_directors',
        #     # Actors dictionary (key: imdbid, value: name)
        #     u'nfo_actor': u'imdb_actors',
        # }

        # extra_imdb_fields = ['imdb_url',
        #                      # 'imdb_photo',
        #                      'imdb_languages']

        # Add imdb entries with single value
        for nfo_name, imdb_name in single_field_mapping.items():
            if nfo_name in fields:
                fields[imdb_name] = fields[nfo_name]

        # Add imdb fields with multiple values
        if 'nfo_genre' in fields:
            fields[u'imdb_genres'] = fields[u'nfo_genre']

        # The nfo file can also have actors and directors, but there is no gain
        # replacing the the values we got from the IMDB lookup.

    def get_nfo_filename(self, entry):
        """
        Get the filename of the nfo file from the 'location' in the entry.

        Returns
        -------
        str | None
            The file name of the 'nfo' file, or None it there is no 'nfo' file.
        """
        location = entry.get('location')
        nfo_full_filename = os.path.splitext(location)[0] + self.nfo_file_extension

        if os.path.isfile(nfo_full_filename):
            return nfo_full_filename
        else:
            return None


class NfoReader(object):
    """
    Class in charge of reading the '.nfo' file and getting a dictionary of
    fields.

    The '.nfo' file is an XML file. Some fields can only appear once, such as
    'title', 'id', 'plot', etc. These fields are listed in the
    `single_value_fields` class attribute. Other fields can appear multiple
    times (with different values), such as 'thumb', 'genre', etc. These fields
    are listed in the `multiple_value_fields` class attribute.
    """

    # xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    # Fields that will be read from the nfo file. The corresponding field in
    # the entry will be nfo_{0} for each field name in these two lists.

    # Fields that appear only once in the nfo file
    single_value_fields = ["title", "originaltitle", "sorttitle", "rating",
                           "year", "votes", "plot", "runtime",
                           "id", "filenameandpath", "trailer"]

    # Fields that can appear multiple times in the nfo file
    multiple_value_fields = ["thumb", "genre", "director", "actor"]
    # xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

    @staticmethod
    def _extract_single_field(root, name, getter_func=lambda x: x.text):
        """
        Use this method to get fields from the root XML tree that only appear once,
        such as 'title', 'year', etc.
        """
        f = root.find(name)
        if f is not None:
            return getter_func(f)
        else:
            return None

    @staticmethod
    def _extract_multiple_field(root, name, getter_func=lambda x: x.text):
        """
        Use this method to get fields from the root XML tree that can appear more
        than once, such as 'actor', 'genre', 'director', etc. The result will
        be a list of values.
        """
        if name == 'actor':
            values = []
        else:
            values = [getter_func(i) for i in root.findall(name)]

        if len(values) > 0:
            return values
        else:
            return None

    @staticmethod
    def get_fields_from_nfo_file(nfo_filename):
        """
        Returns a dictionary with all firlds read from the '.nfo' file.

        The keys are named as 'nfo_something'.
        """
        d = {}
        if os.path.exists(nfo_filename):
            tree = ET.parse(nfo_filename)
            root = tree.getroot()

            # TODO: Right now it only works for movies
            if root.tag != 'movie':
                return d

            # TODO: Get more metadata from the nfo file

            # Single value fields
            for field_name in NfoReader.single_value_fields:
                nfo_field_name = u'nfo_{0}'.format(field_name)
                value = NfoReader._extract_single_field(root, field_name)
                if value is not None:
                    d[nfo_field_name] = value

            # Multiple value fields (genres, actors, directors)
            for field_name in NfoReader.multiple_value_fields:
                nfo_field_name = u'nfo_{0}'.format(field_name)
                values = NfoReader._extract_multiple_field(root, field_name)
                if values is not None:
                    d[nfo_field_name] = values
        return d


class _ImdbFiller(object):

    pass


@event('plugin.register')
def register_plugin():
    plugin.register(NfoLookup, 'nfo_lookup', api_ver=2)
