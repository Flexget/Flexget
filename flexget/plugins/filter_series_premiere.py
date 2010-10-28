import logging
from flexget.utils import qualities
from flexget.manager import Base
from sqlalchemy import Column, Integer, Unicode
from flexget.plugin import register_plugin, priority

log = logging.getLogger('series_premiere')


class SeriesPremiere(Base):

    __tablename__ = 'series_premieres'

    id = Column(Integer, primary_key=True)
    series_name = Column(Unicode, index=True)

    def __repr__(self):
        return '<series_premieres(series_name=%s)>' % (self.series_name)


class FilterSeriesPremiere(object):
    """
    Accept an entry that appears to be the first episode of any series.

    Examples:

    series_premiere: yes

    series_premiere: ~/Media/TV/_NEW_/.

    series_premiere:
      path: ~/Media/TV/_NEW_/.

    NOTE: this plugin only looks in the entry title and expects the title
    format to start with the series name followed by the episode info. Use
    the manipulate plugin to modify the entry title to match this format, if
    necessary.

    TODO:
        - integrate thetvdb to allow refining by genres, etc.
        - handle propers
    """

    # Run after filter_series which has the default priority of 128.
    @priority(127)
    def validator(self):
        """Return config validator"""
        from flexget import validator
        config = validator.factory()
        config.accept('path', allow_replacement=True)
        config.accept('boolean')
        advanced = config.accept('dict')
        advanced.accept('path', key='path', allow_replacement=True)
        return config

    def get_config(self, feed):
        config = feed.config.get('series_premiere', {})
        if isinstance(config, basestring):
            config = {'path': config, 'enabled': True}
        elif isinstance(config, bool):
            config = {'enabled': config}
        return config

    def on_feed_filter(self, feed):
        config = self.get_config(feed)
        # Store found premieres in {series_name: (quality, entry)} format
        found_premieres = {}
        for entry in feed.entries:
            # Skip if this entry is accepted or controlled by the series plugin
            if not entry.get('series_name') or not entry.get('series_guessed') or entry in feed.accepted:
                continue
            # Skip the entry if it is not a premier
            if entry.get('series_season') != 1 or entry.get('series_episode') != 1:
                continue

            qual = qualities.get(entry.get('quality'))
            # If we have already seen a better quality of this premier, skip this one
            if entry['series_name'] in found_premieres and \
                qual <= found_premieres[entry['series_name']][0]:
                continue

            found_premieres[entry['series_name']] = (qual, entry)

        if not found_premieres:
            return

        # Accept all the premieres we found
        for entry in [e[1] for e in found_premieres.itervalues()]:
            premiere = feed.session.query(SeriesPremiere).filter(SeriesPremiere.series_name == unicode(entry['series_name']).lower()).first()
            if premiere:
                continue

            if 'path' in config:
                try:
                    path = config['path'] % entry
                    entry['path'] = path
                except KeyError, e:
                    log.error("Could not set path for %s: does not contain the field '%s'." % (entry['title'], e))

            feed.accept(entry, 'series premiere episode')
            log.debug("Premiere found for: %s" % (entry['series_name']))

            premiere = SeriesPremiere()
            premiere.series_name = unicode(entry['series_name']).lower()
            feed.session.add(premiere)

register_plugin(FilterSeriesPremiere, 'series_premiere')
