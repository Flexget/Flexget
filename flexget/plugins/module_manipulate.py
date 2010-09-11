import logging
import re
from flexget.plugin import priority, register_plugin

log = logging.getLogger('manipulate')


class Manipulate(object):
    """
        Usage:
        
        manipulate:
          - <destination field>:
              [from]: <source field>
              [extract]: <regexp>
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
        bundle.reject_keys(['from', 'extract', 'replace'],
            'Option \'$key\' has invalid indentation level. It needs 2 more spaces.')
        edit = bundle.accept_any_key('dict')
        edit.accept('text', key='from')
        edit.accept('regexp', key='extract')
        replace = edit.accept('dict', key='replace')
        replace.accept('regexp', key='regexp', required=True)
        replace.accept('text', key='format', required=True)
        return root

    @priority(255)
    def on_feed_filter(self, feed):
        for entry in feed.entries + feed.rejected:
            self.process(feed, entry)

    def process(self, feed, entry):
        config = feed.config['manipulate']

        for item in config:
            for field, config in item.iteritems():
                from_field = field
                if 'from' in config:
                    from_field = config['from']
                field_value = entry.get(from_field)
                log.debug('field: %s from_field: %s field_value: %s' % (field, from_field, field_value))

                if 'extract' in config:
                    if not field_value:
                        log.warning('Cannot extract, field %s is not present' % from_field)
                        continue
                    match = re.match(config['extract'], field_value)
                    if match:
                        groups = [x for x in match.groups() if x is not None]
                        log.debug('groups: %s' % groups)
                        field_value = ''.join(groups)
                        log.debug('field %s after extract: %s' % (field, field_value))

                if 'replace' in config:
                    if not field_value:
                        log.warning('Cannot replace, field %s is not present' % from_field)
                        continue
                    replace_config = config['replace']
                    field_value = re.sub(replace_config['regexp'], replace_config['format'], field_value)
                    log.debug('field %s after replace: %s' % (field, field_value))

                entry[field] = field_value
                feed.verbose_details('Field %s is now %s' % (field, entry[field]))

register_plugin(Manipulate, 'manipulate')
