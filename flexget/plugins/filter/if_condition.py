import logging
import re
import datetime
from copy import copy
from flexget.feed import Feed
from flexget.plugin import register_plugin, get_plugins_by_phase, get_plugin_by_name, priority

log = logging.getLogger('if')


def safer_eval(statement, locals):
    """A safer eval function. Does not allow __ or try statements, only includes certain 'safe' builtins."""
    allowed_builtins = ['True', 'False', 'str', 'unicode', 'int', 'float', 'len', 'any', 'all']
    for name in allowed_builtins:
        locals[name] = globals()['__builtins__'].get(name)
    if re.search(r'__|try\s*:', statement):
        raise ValueError('\'__\' or try blocks not allowed in if statements.')
    return eval(statement, {'__builtins__': None}, locals)


class FilterIf(object):
    """Can run actions on entries that satisfy a given condition.

    Actions include accept, reject, and fail, as well as the ability to run other filter plugins on the entries."""

    def validator(self):
        from flexget import validator
        root = validator.factory('list')
        key_validator = validator.factory('regexp_match',
                                          message='If statements cannot contain \'__\' or \'try\' statements')
        key_validator.reject(r'.*?(__|try\s*:)')
        key_validator.accept('.')
        action = root.accept('dict').accept_valid_keys('root', key_validator=key_validator)
        action.accept('choice').accept_choices(['accept', 'reject', 'fail'])
        filter_action = action.accept('dict')
        # Get a list of apiv2 input plugins, make sure to exclude self
        valid_filters = [plugin for plugin in get_plugins_by_phase('filter')
                         if plugin.api_ver > 1 and plugin.name != 'if']
        # Build a dict validator that accepts the available filter plugins and their settings
        for plugin in valid_filters:
            if hasattr(plugin.instance, 'validator'):
                validator = plugin.instance.validator()
                if validator.name == 'root':
                    # If a root validator is returned, grab the list of child validators
                    filter_action.valid[plugin.name] = validator.valid
                else:
                    filter_action.valid[plugin.name] = [plugin.instance.validator()]
            else:
                filter_action.valid[plugin.name] = [validator.factory('any')]
        return root

    @priority(80)
    def on_feed_filter(self, feed, config):
        entry_actions = {
            'accept': feed.accept,
            'reject': feed.reject,
            'fail': feed.fail}
        for entry in feed.entries:
            # Make entry fields and other utilities available in the eval namespace
            # We need our namespace to be an Entry instance for lazy loading to work
            eval_locals = copy(entry)
            eval_locals.update({'has_field': lambda f: f in entry,
                                'timedelta': datetime.timedelta,
                                'now': datetime.datetime.now()})
            for item in config:
                requirement, action = item.items()[0]
                try:
                    # Restrict eval namespace to have no globals and locals only from eval_locals
                    passed = safer_eval(requirement, eval_locals)
                except NameError, e:
                    # Extract the name that did not exist
                    missing_field = e.message.split('\'')[1]
                    log.debug('%s does not contain the field %s' % (entry['title'], missing_field))
                except Exception, e:
                    log.error('Error occurred in if statement: %r' % e)
                else:
                    if passed:
                        log.debug('%s matched requirement %s' % (entry['title'], requirement))
                        if isinstance(action, basestring):
                            # Simple entry action (accept, reject or fail) was specified as a string
                            entry_actions[action](entry, 'Matched requirement: %s' % requirement)
                        else:
                            # Other filters were specified to run on this entry
                            fake_feed = Feed(feed.manager, feed.name, feed.config)
                            fake_feed.session = feed.session
                            fake_feed.entries = [entry]
                            try:
                                for filter_name, filter_config in action.iteritems():
                                    filter = get_plugin_by_name(filter_name)
                                    method = filter.phase_handlers['filter']
                                    method(fake_feed, filter_config)
                            except Exception:
                                raise
                            else:
                                # Populate changes from the fake feed to the real one
                                for e in fake_feed.accepted:
                                    feed.accept(e, e.get('reason'))
                                for e in fake_feed.rejected:
                                    feed.reject(e, e.get('reason'))
                                for e in fake_feed.failed:
                                    feed.fail(e, e.get('reason'))


register_plugin(FilterIf, 'if', api_ver=2)
