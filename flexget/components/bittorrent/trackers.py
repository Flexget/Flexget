import re

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='modify_torrents')


class AddTrackers:
    """
        Adds tracker URL to torrent files.

        Configuration example:

        add_trackers:
          - uri://tracker_address:port/

        This will add all tracker URL uri://tracker_address:port/.
    """

    schema = {'type': 'array', 'items': {'type': 'string', 'format': 'url'}}

    @plugin.priority(127)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                for url in config:
                    if url not in entry['torrent'].trackers:
                        entry['torrent'].add_multitracker(url)
                        logger.info('Added {} tracker to {}', url, entry['title'])
            if entry['url'].startswith('magnet:'):
                entry['url'] += ''.join(['&tr=' + url for url in config])


class RemoveTrackers:
    """
        Removes trackers from torrent files using regexp matching.

        Configuration example:

        remove_trackers:
          - moviex

        This will remove all trackers that contain text moviex in their url.
    """

    schema = {'type': 'array', 'items': {'type': 'string', 'format': 'regex'}}

    @plugin.priority(127)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                for tracker in entry['torrent'].trackers:
                    for regexp in config or []:
                        if re.search(regexp, tracker, re.IGNORECASE | re.UNICODE):
                            logger.debug(
                                'remove_trackers removing {} because of {}', tracker, regexp
                            )
                            # remove tracker
                            entry['torrent'].remove_multitracker(tracker)
                            logger.info('Removed {}', tracker)
            if entry['url'].startswith('magnet:'):
                for regexp in config:
                    # Replace any tracker strings that match the regexp with nothing
                    tr_search = r'&tr=([^&]*%s[^&]*)' % regexp
                    entry['url'] = re.sub(tr_search, '', entry['url'], re.IGNORECASE | re.UNICODE)


class ModifyTrackers:
    """
    Modify tracker URL to torrent files.

    Configuration example::

        modify_trackers:
          - SearchAndReplace:
              from: string_to_search
              to: string_to_replace

    """

    schema = {
        'type': 'array',
        'items': {
            'type': 'object',
            'additionalProperties': {
                'type': 'object',
                'properties': {'from': {'type': 'string'}, 'to': {'type': 'string'}},
                'additionalProperties': False,
            },
            'maxProperties': 1,
        },
    }

    @plugin.priority(127)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                torrent = entry['torrent']
                trackers = torrent.trackers
                for item in config:
                    for replace in item.values():
                        for tracker in trackers:
                            if replace.get('from') in tracker:
                                torrent.remove_multitracker(tracker)
                                trackernew = tracker.replace(
                                    replace.get('from'), replace.get('to')
                                )
                                torrent.add_multitracker(trackernew)
                                logger.info('Modify {} in {}', tracker, trackernew)


@event('plugin.register')
def register_plugin():
    plugin.register(AddTrackers, 'add_trackers', api_ver=2)
    plugin.register(RemoveTrackers, 'remove_trackers', api_ver=2)
    plugin.register(ModifyTrackers, 'modify_trackers', api_ver=2)
