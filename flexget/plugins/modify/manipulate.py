import logging
import re
from flexget.plugin import priority, register_plugin

log = logging.getLogger('manipulate')


class Manipulate(object):
    """
    Usage:

      manipulate:
        - <destination field>:
            [phase]: <phase>
            [from]: <source field>
            [extract]: <regexp>
            [separator]: <text>
            [replace]:
              regexp: <regexp>
              format: <regexp>

    Example:

      manipulate:
        - title:
            extract: \[\d\d\d\d\](.*)
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        bundle = root.accept('list').accept('dict')
        # prevent invalid indentation level
        bundle.reject_keys(['from', 'extract', 'replace', 'phase'],
            'Option \'$key\' has invalid indentation level. It needs 2 more spaces.')
        edit = bundle.accept_any_key('dict')
        edit.accept('choice', key='phase').accept_choices(['metainfo', 'filter'], ignore_case=True)
        edit.accept('text', key='from')
        edit.accept('regexp', key='extract')
        edit.accept('text', key='separator')
        replace = edit.accept('dict', key='replace')
        replace.accept('regexp', key='regexp', required=True)
        replace.accept('text', key='format', required=True)
        return root

    def on_feed_start(self, feed):
        """Separates the config into a dict with a list of jobs per phase."""
        config = feed.config['manipulate']
        self.phase_jobs = {'filter': [], 'metainfo': []}
        for item in config:
            for item_config in item.itervalues():
                # Get the phase specified for this item, or use default of metainfo
                phase = item_config.get('phase', 'metainfo')
                self.phase_jobs[phase].append(item)

    @priority(255)
    def on_feed_metainfo(self, feed):
        if not self.phase_jobs['metainfo']:
            # return if no jobs for this phase
            return
        for entry in feed.entries:
            self.process(feed, entry, self.phase_jobs['metainfo'])

    @priority(255)
    def on_feed_filter(self, feed):
        if not self.phase_jobs['filter']:
            # return if no jobs for this phase
            return
        for entry in feed.entries + feed.rejected:
            self.process(feed, entry, self.phase_jobs['filter'])

    def process(self, feed, entry, jobs):

        for item in jobs:
            for field, config in item.iteritems():
                from_field = field
                if 'from' in config:
                    from_field = config['from']
                field_value = entry.get(from_field)
                log.debug('field: `%s` from_field: `%s` field_value: `%s`' % (field, from_field, field_value))

                if 'extract' in config:
                    if not field_value:
                        log.warning('Cannot extract, field `%s` is not present' % from_field)
                        continue
                    match = re.search(config['extract'], field_value)
                    if match:
                        groups = [x for x in match.groups() if x is not None]
                        log.debug('groups: %s' % groups)
                        field_value = config.get('separator', ' ').join(groups).strip()
                        log.debug('field `%s` after extract: `%s`' % (field, field_value))

                if 'replace' in config:
                    if not field_value:
                        log.warning('Cannot replace, field `%s` is not present' % from_field)
                        continue
                    replace_config = config['replace']
                    field_value = re.sub(replace_config['regexp'], replace_config['format'], field_value).strip()
                    log.debug('field `%s` after replace: `%s`' % (field, field_value))

                entry[field] = field_value
                log.verbose('Field `%s` is now `%s`' % (field, entry[field]))

register_plugin(Manipulate, 'manipulate')
