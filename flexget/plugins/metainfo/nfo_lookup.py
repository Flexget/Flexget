import os
import xml.etree.ElementTree as ET

from loguru import logger

from flexget import plugin
from flexget.event import event

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.imdb.utils import is_valid_imdb_title_id
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='imdb')


logger = logger.bind(name='nfo_lookup')


class NfoLookup:
    """
    Retrieves information from a local '.nfo' info file.

    The read metadata will be add as 'nfo_something' in the entry. Also, if an 'id' is found in the '.nfo' file then the
    'imdb_id' field will be set to its value. This means that if the imdb_lookup plugin is used in addition to this
    plugin it will be able to use the ID from '.nfo' file to get the correct movie.

    The nfo file is used by Kodi.

    Example:
        nfo_lookup: yes

    WARNING: This plugin will read a file with extension '.nfo' and the same name as the entry filename as an XML file
    using xml.etree.ElementTree from the standard python library. As such, it is vulnerable to XML vulnerabilities
    described in the link below
    https://docs.python.org/3/library/xml.html#xml-vulnerabilities

    Use this only with nfo files you have created yourself.
    """

    schema = {'type': 'boolean'}
    nfo_file_extension = '.nfo'

    # This priority makes sure this plugin runs before the imdb_lookup plugin, if it is also used. That way setting
    # imdb_id here will help imdb_lookup find the correct movie.
    @plugin.priority(150)
    def on_task_metainfo(self, task, config):
        # check if disabled (value set to false)
        if not config:
            # Config was set to 'no' instead of yes. Don't do anything then.
            return

        for entry in task.entries:
            # If this entry was obtained from the filesystem plugin it should have a filename field. If it does not have
            # one then there is nothing we can do in this plugin.
            filename = entry.get('filename')
            location = entry.get('location')

            # If there is no 'filename' field there is also no nfo file
            if filename is None or location is None:
                logger.warning(
                    "Entry {} didn't come from the filesystem plugin", entry.get('title')
                )
                continue
            else:
                # This will be None if there is no nfo file
                nfo_filename = self.get_nfo_filename(entry)
                if nfo_filename is None:
                    logger.warning(
                        'Entry {} has no corresponding {} file',
                        entry.get('title'),
                        self.nfo_file_extension,
                    )
                    continue

            # Populate the fields from the information in the .nfo file Note that at this point `nfo_filename` has the
            # name of an existing '.nfo' file
            self.lookup(entry, nfo_filename)

    def lookup(self, entry, nfo_filename):
        # If there is already data from a previous parse then we don't need to do anything
        if entry.get('nfo_id') is not None:
            logger.warning(
                'Entry {} was already parsed by nfo_lookup and it will be skipped. ',
                entry.get('title'),
            )
            return

        # nfo_filename Should not be None at this point
        assert nfo_filename is not None

        # Get all values we can from the nfo file. If the nfo file can't be parsed then a warning is logged and we
        # return without changing the entry
        try:
            nfo_reader = NfoReader(nfo_filename)
            fields = nfo_reader.get_fields_from_nfo_file()
        except BadXmlFile:
            logger.warning("Invalid '.nfo' file for entry {}", entry.get('title'))
            return

        entry.update(fields)

        # If a valid IMDB id was found in the nfo file, set the imdb_id field of the entry. This will help the
        # imdb_lookup plugin to get the correct data if it is also used.
        if 'nfo_id' in fields:
            if is_valid_imdb_title_id(entry.get('nfo_id', '')):
                entry.update({'imdb_id': fields['nfo_id']})
            else:
                logger.warning(
                    "ID found in nfo file for entry '{}', but it was not a valid IMDB ID",
                    entry.get('title'),
                )

    def get_nfo_filename(self, entry):
        """
        Get the filename of the nfo file from the 'location' in the entry.

        Returns
        -------
        str
            The file name of the 'nfo' file, or None it there is no 'nfo' file.
        """
        location = entry.get('location')
        nfo_full_filename = os.path.splitext(location)[0] + self.nfo_file_extension

        if os.path.isfile(nfo_full_filename):
            return nfo_full_filename


class BadXmlFile(Exception):
    """
    Exception that is raised if the nfo file can't be parsed due to some invalid nfo file.
    """

    pass


class NfoReader:
    """
    Class in charge of parsing the '.nfo' file and getting a dictionary of fields.

    The '.nfo' file is an XML file. Some fields can only appear once, such as 'title', 'id', 'plot', etc., while other
    fields can appear multiple times (with different values), such as 'thumb', 'genre', etc. These fields are listed in
    the `_fields` attribute.
    """

    def __init__(self, filename):
        try:
            tree = ET.parse(filename)
            root = tree.getroot()
        except ET.ParseError:
            raise BadXmlFile()

        if os.path.exists(filename):
            self._nfo_filename = filename
            self._root = root
        else:
            raise BadXmlFile()

        # Each key in the dictionary correspond to a field that should be read from the nfo file. The values are a tuple
        # with a boolean and a callable. The boolean indicates if the field can appear multiple times, while the
        # callable is a function to read the field value from the XML element.
        #
        # In the future we could extend the nfo_lookup plugin to accept 'set' in its configuration to add new entries to
        # this dictionary to handle other tags in the nfo file and add the data to the entry.
        self._fields = {
            "title": (False, NfoReader._single_elem_getter_func),
            "originaltitle": (False, NfoReader._single_elem_getter_func),
            "sorttitle": (False, NfoReader._single_elem_getter_func),
            "rating": (False, NfoReader._single_elem_getter_func),
            "year": (False, NfoReader._single_elem_getter_func),
            "votes": (False, NfoReader._single_elem_getter_func),
            "plot": (False, NfoReader._single_elem_getter_func),
            "runtime": (False, NfoReader._single_elem_getter_func),
            "id": (False, NfoReader._single_elem_getter_func),
            "filenameandpath": (False, NfoReader._single_elem_getter_func),
            "trailer": (False, NfoReader._single_elem_getter_func),
            "thumb": (True, NfoReader._single_elem_getter_func),
            "genre": (True, NfoReader._single_elem_getter_func),
            "director": (True, NfoReader._single_elem_getter_func),
            # Actor field has child elements, such as 'name' and 'role'
            "actor": (True, NfoReader._composite_elem_getter_func),
            "studio": (True, NfoReader._single_elem_getter_func),
            "country": (True, NfoReader._single_elem_getter_func),
        }

    @staticmethod
    def _single_elem_getter_func(x):
        """
        Method to get the text value of simple XML element that does not contain child nodes.
        """
        return x.text

    @staticmethod
    def _composite_elem_getter_func(x):
        """
        Method to get XML elements that have children as a dictionary.
        """
        return {i.tag: i.text for i in x}

    def _extract_single_field(self, name, getter_func):
        """
        Use this method to get fields from the root XML tree that only appear once, such as 'title', 'year', etc.
        """
        f = self._root.find(name)
        if f is not None:
            return getter_func(f)

    def _extract_multiple_field(self, name, getter_func):
        """
        Use this method to get fields from the root XML tree that can appear more than once, such as 'actor', 'genre',
        'director', etc. The result will be a list of values.
        """
        values = [getter_func(i) for i in self._root.findall(name)]

        if len(values) > 0:
            return values

    def get_fields_from_nfo_file(self):
        """
        Returns a dictionary with all firlds read from the '.nfo' file.

        The keys are named as 'nfo_something'.
        """
        d = {}
        if self._root is None:
            return d

        # TODO: Right now it only works for movies
        if self._root.tag != 'movie':
            return d

        for name, values in self._fields.items():
            multiple_bool = values[0]
            getter_func = values[1]

            nfo_field_name = f'nfo_{name}'

            if multiple_bool:
                v = self._extract_multiple_field(name, getter_func)
            else:
                v = self._extract_single_field(name, getter_func)

            if v is not None:
                d[nfo_field_name] = v

        return d


@event('plugin.register')
def register_plugin():
    plugin.register(NfoLookup, 'nfo_lookup', api_ver=2)
