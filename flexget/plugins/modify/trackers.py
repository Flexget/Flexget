from __future__ import unicode_literals, division, absolute_import
import logging
import re
from flexget.plugin import priority, register_plugin

log = logging.getLogger('modify_torrents')


class AddTrackers(object):

    """
        Adds tracker URL to torrent files.

        Configuration example:

        add_trackers:
          - uri://tracker_address:port/

        This will add all tracker URL uri://tracker_address:port/.
    """

    def validator(self):
        from flexget import validator
        trackers = validator.factory('list')
        trackers.accept('url', protocols=['udp', 'http'])
        return trackers

    @priority(127)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                for url in config:
                    if not url in entry['torrent'].trackers:
                        entry['torrent'].add_multitracker(url)
                        log.info('Added %s tracker to %s' % (url, entry['title']))
            if entry['url'].startswith('magnet:'):
                entry['url'] += ''.join(['&tr=' + url for url in config])


class RemoveTrackers(object):

    """
        Removes trackers from torrent files using regexp matching.

        Configuration example:

        remove_trackers:
          - moviex

        This will remove all trackers that contain text moviex in their url.
    """

    def validator(self):
        from flexget import validator
        trackers = validator.factory('list')
        trackers.accept('regexp')
        return trackers

    @priority(127)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                for tracker in entry['torrent'].trackers:
                    for regexp in config or []:
                        if re.search(regexp, tracker, re.IGNORECASE | re.UNICODE):
                            log.debug('remove_trackers removing %s because of %s' % (tracker, regexp))
                            # remove tracker
                            entry['torrent'].remove_multitracker(tracker)
                            log.info('Removed %s' % tracker)
            if entry['url'].startswith('magnet:'):
                for regexp in config:
                    # Replace any tracker strings that match the regexp with nothing
                    tr_search = r'&tr=([^&]*%s[^&]*)' % regexp
                    entry['url'] = re.sub(tr_search, '', entry['url'], re.IGNORECASE | re.UNICODE)


class ModifyTrackers(object):

    """
        Modify tracker URL to torrent files.

        Configuration example:

        modify_trackers:
          - SearchAndReplace1
              from: string_to_search
              to: string_to_replace

    """

    def validator(self):
        from flexget import validator
        trackers = validator.factory()
        bundle = trackers.accept('list').accept('dict')
        # prevent invalid indentation level
        bundle.reject_keys(['from', 'to'],
                           'Option \'$key\' has invalid indentation level. It needs 2 more spaces.')
        edit = bundle.accept_any_key('dict')
        edit.accept('text', key='from', required=True)
        edit.accept('text', key='to', required=True)
        return trackers

    @priority(127)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                torrent = entry['torrent']
                trackers = torrent.trackers
                for item in config:
                    for replace in item.itervalues():
                        for tracker in trackers:
                            if replace.get('from') in tracker:
                                torrent.remove_multitracker(tracker)
                                trackernew = tracker.replace(replace.get('from'), replace.get('to'))
                                torrent.add_multitracker(trackernew)
                                log.info('Modify %s in %s' % (tracker, trackernew))


register_plugin(AddTrackers, 'add_trackers', api_ver=2)
register_plugin(RemoveTrackers, 'remove_trackers', api_ver=2)
register_plugin(ModifyTrackers, 'modify_trackers', api_ver=2)
