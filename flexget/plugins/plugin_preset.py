import logging
from flexget.plugin import *

log = logging.getLogger('preset')


class PluginPreset(object):
    """
        Use presets.

        Example:

        preset: movies

        Example, list of presets:

        preset:
          - movies
          - imdb
    """

    def __init__(self):
        self.warned = False

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('text')
        root.accept('boolean')
        presets = root.accept('list')
        presets.accept('text')
        return root

    @priority(255)
    def on_process_start(self, feed):
        config = feed.config.get('preset', 'global')
        if isinstance(config, basestring):
            config = [config]
        elif isinstance(config, bool): # handles 'preset: no' form to turn off preset on this feed
            if not config:
                return

        # implements --preset NAME
        if feed.manager.options.preset:
            if feed.manager.options.preset not in config:
                feed.enabled = False
                return

        # add global in except when disabled with no_global
        if 'no_global' in config:
            config.remove('no_global')
            if 'global' in config:
                config.remove('global')
        elif not 'global' in config:
            config.append('global')

        log.debugall('presets: %s' % config)

        toplevel_presets = feed.manager.config.get('presets', {})

        # check for indentation error (plugin as a preset)
        if (feed.manager.options.test or feed.manager.options.validate) and not self.warned:
            plugins = get_plugin_keywords()
            for name in toplevel_presets.iterkeys():
                if name in plugins:
                    log.warning('Plugin \'%s\' seems to be in the wrong place? You probably wanted to put it in a preset. Please fix the indentation level!' % name)
            self.warned = True

        # apply presets
        for preset in config:
            if preset != 'global':
                log.debug('Merging preset %s into feed %s' % (preset, feed.name))
            if not preset in toplevel_presets:
                if preset == 'global':
                    continue
                raise PluginError('Unable to find preset %s for feed %s' % (preset, feed.name), log)
            # merge
            from flexget.utils.tools import MergeException, merge_dict_from_to
            try:
                merge_dict_from_to(toplevel_presets[preset], feed.config)
            except MergeException:
                raise PluginError('Failed to merge preset %s to feed %s, incompatible datatypes' % (preset, feed.name))


class DisablePlugin(object):
    """
    Allows disabling plugins when using presets.

    Example:

        presets:
          movies:
            download: ~/torrents/movies/
            .
            .

        feeds:
          nzbs:
            preset: movies
            disable_plugin:
              - download
            sabnzbd:
              .
              .

        Feed nzbs uses all other configuration from preset movies but removes the download plugin
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('text')
        presets = root.accept('list')
        presets.accept('text')
        return root

    @priority(250)
    def on_feed_start(self, feed):
        config = feed.config['disable_plugin']
        if isinstance(config, basestring):
            config = [config]
        # let's disable them
        for disable in config:
            if disable in feed.config:
                log.debug('disabling %s' % disable)
                del(feed.config[disable])

register_plugin(PluginPreset, 'preset', builtin=True)
register_plugin(DisablePlugin, 'disable_plugin')

register_parser_option('--preset', action='store', dest='preset', default=False,
                       metavar='NAME', help='Execute feeds with given preset.')
