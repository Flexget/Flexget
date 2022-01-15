import re
import unicodedata
from datetime import date, datetime, timedelta

from loguru import logger
from requests.exceptions import HTTPError, RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import Session as RequestSession
from flexget.utils.requests import TimedLimiter
from flexget.utils.soup import get_soup

logger = logger.bind(name='search_npo')

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('npostart.nl', '6 seconds'))
requests.add_domain_limiter(TimedLimiter('npo.nl', '6 seconds'))


class NPOWatchlist:
    """
    Produces entries for every episode on the user's npostart.nl watchlist (Dutch public television).
    Entries can be downloaded using http://arp242.net/code/download-npo

    If 'remove_accepted' is set to 'yes', the plugin will delete accepted entries from the watchlist after download
        is complete.
    If 'max_episode_age_days' is set (and not 0), entries will only be generated for episodes broadcast in the last
        x days.  This only applies to episodes related to series the user is following.
    If 'download_premium' is set to 'yes', the plugin will also download entries that are marked as exclusive
        content for NPO Plus subscribers.

    For example:
        npo_watchlist:
          email: aaaa@bbb.nl
          password: xxx
          remove_accepted: yes
          max_episode_age_days: 7
          download_premium: no
        accept_all: yes
        exec:
          fail_entries: yes
          auto_escape: yes
          on_output:
            for_accepted:
              - download-npo -o "path/to/directory/{{series_name_plain}}" -f "{serie_titel} - {datum} \
                  {aflevering_titel} ({episode_id})" -t {{url}}
        """

    schema = {
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'password': {'type': 'string'},
            'remove_accepted': {'type': 'boolean', 'default': False},
            'max_episode_age_days': {'type': 'integer', 'default': -1},
            'download_premium': {'type': 'boolean', 'default': False},
        },
        'required': ['email', 'password'],
        'additionalProperties': False,
    }

    csrf_token = None

    def _convert_plain(self, s):
        return ''.join(
            c
            for c in unicodedata.normalize('NFD', s)
            if not re.match('Mn|P[^cd]', unicodedata.category(c))
        )

    def _parse_date(self, date_text):
        return datetime.strptime(date_text, '%d-%m-%Y').date()

    def _get_page(self, task, config, url):
        self._login(task, config)
        try:
            logger.debug('Fetching NPO profile page: {}', url)
            page_response = requests.get(url)
            if page_response.url != url:
                raise plugin.PluginError(
                    'Unexpected page: {} (expected {})'.format(page_response.url, url)
                )
            return page_response
        except RequestException as e:
            raise plugin.PluginError('Request error: %s' % str(e))

    def _login(self, task, config):
        if 'isAuthenticatedUser' in requests.cookies:
            logger.debug('Already logged in')
            return

        npostart_login_url = 'https://www.npostart.nl/login'
        npoid_base = 'https://id.npo.nl'
        npoid_login_url = 'https://id.npo.nl/account/login'

        try:
            login_response = requests.get(npostart_login_url)
            if not login_response.url.startswith(npoid_login_url):
                raise plugin.PluginError('Unexpected login page: {}'.format(login_response.url))

            login_page = get_soup(login_response.content)
            token = login_page.find('input', attrs={'name': '__RequestVerificationToken'})['value']
            return_url = login_page.find('input', attrs={'name': 'ReturnUrl'})['value']

            email = config.get('email')
            password = config.get('password')

            npoid_response = requests.post(
                npoid_login_url,
                {
                    'button': 'login',
                    '__RequestVerificationToken': token,
                    'ReturnUrl': return_url,
                    'EmailAddress': email,
                    'Password': password,
                },
            )

            npostart_response = requests.get(npoid_base + return_url)

            if 'isAuthenticatedUser' not in requests.cookies:
                raise plugin.PluginError('Failed to login. Check username and password.')
            logger.debug('Succesfully logged in: {}', email)
        except RequestException as e:
            raise plugin.PluginError('Request error: %s' % str(e))

    def _get_favourites_entries(self, task, config, profileId):
        # Details of profile using the $profileId:
        # https://www.npostart.nl/api/account/@me/profile/$profileId  (?refresh=1)
        # XMLHttpRequest could also be done on, but is not reliable, because if a series is
        # bookmarked after episode is already broadcasted, it does not appear in this list.
        # https://www.npostart.nl/ums/accounts/@me/favourites/episodes?dateFrom=2018-06-04&dateTo=2018-06-05
        profile_details_url = 'https://www.npostart.nl/api/account/@me/profile/'

        entries = []
        try:
            profile = requests.get(profile_details_url + profileId).json()
            logger.info('Retrieving favorites for profile {}', profile['name'])
            for favourite in profile['favourites']:
                if favourite['mediaType'] == 'series':
                    entries += self._get_series_episodes(task, config, favourite['mediaId'])
        except RequestException as e:
            raise plugin.PluginError('Request error: %s' % str(e))
        return entries

    def _get_series_episodes(self, task, config, mediaId, series_info=None, page=1):
        episode_tiles_url = 'https://www.npostart.nl/media/series/{0}/episodes'
        episode_tiles_parameters = {
            'page': str(page),
            'tileMapping': 'dedicated',
            'tileType': 'asset',
        }
        entries = []

        if not series_info:
            series_info = self._get_series_info(task, config, mediaId)
            if not series_info:  # if fetching series_info failed, return empty entries
                logger.error('Failed to fetch series information for {}, skipping series', mediaId)
                return entries

        headers = {
            'Origin': 'https://www.npostart.nl',
            'X-XSRF-TOKEN': requests.cookies['XSRF-TOKEN'],
            'X-Requested-With': 'XMLHttpRequest',
        }
        if page > 1:
            headers['Referer'] = episode_tiles_url.format(mediaId) + '?page={0}'.format(
                page - 1
            )  # referer from prev page

        logger.debug(
            'Retrieving episodes page {} for {} ({})', page, series_info['npo_name'], mediaId
        )
        try:
            episodes = requests.get(
                episode_tiles_url.format(mediaId), params=episode_tiles_parameters, headers=headers
            ).json()
            new_entries = self._parse_tiles(task, config, episodes['tiles'], series_info)
            entries += new_entries

            if (
                new_entries and episodes['nextLink']
            ):  # only fetch next page if we accepted any from current page
                logger.debug('NextLink for more episodes: {}', episodes['nextLink'])
                entries += self._get_series_episodes(
                    task,
                    config,
                    mediaId,
                    series_info,
                    page=int(episodes['nextLink'].rsplit('page=')[1]),
                )
        except RequestException as e:
            logger.error('Request error: {}', str(e))  # if it fails, just go to next favourite

        if not entries and page == 1:
            logger.verbose('No new episodes found for {} ({})', series_info['npo_name'], mediaId)
        return entries

    def _get_series_info(self, task, config, mediaId):
        series_info_url = 'https://www.npostart.nl/{0}'
        series_info = None
        logger.verbose('Retrieving series info for {}', mediaId)
        try:
            response = requests.get(series_info_url.format(mediaId))
            logger.debug('Series info found at: {}', response.url)
            page = get_soup(response.content)
            series = page.find('section', class_='npo-header-episode-meta')
            if series:  # sometimes the NPO page does not return valid content
                # create a stub to store the common values for all episodes of this series
                series_info = {
                    'npo_url': response.url,  # we were redirected to the true URL
                    'npo_name': series.find('h1').text,
                    'npo_description': series.find('div', id='metaContent').find('p').text,
                    'npo_language': 'nl',  # hard-code the language as if in NL, for lookup plugins
                    'npo_version': page.find('meta', attrs={'name': 'generator'})['content'],
                }  # include NPO website version
                logger.debug('Parsed series info for: {} ({})', series_info['npo_name'], mediaId)
        except RequestException as e:
            logger.error('Request error: {}', str(e))
        return series_info

    def _parse_tiles(self, task, config, tiles, series_info):
        max_age = config.get('max_episode_age_days')
        download_premium = config.get('download_premium')
        entries = []

        if tiles is not None:
            for tile in tiles:
                # there is only one list_item per tile
                for list_item in get_soup(tile).findAll('div', class_='npo-asset-tile-container'):
                    episode_id = list_item['data-id']
                    premium = 'npo-premium-content' in list_item['class']
                    logger.debug('Parsing episode: {}', episode_id)

                    url = list_item.find('a')['href']
                    # Check if the URL found to the episode matches the expected pattern
                    if len(url.split('/')) != 6:
                        logger.verbose(
                            'Skipping {}, the URL has an unexpected pattern: {}', episode_id, url
                        )
                        continue  # something is wrong; skip this episode

                    episode_name = list_item.find('h2')
                    if episode_name:
                        title = '{} ({})'.format(next(episode_name.stripped_strings), episode_id)
                    else:
                        title = '{}'.format(episode_id)

                    timer = '0'
                    timerdiv = list_item.find('div', class_='npo-asset-tile-timer')
                    if timerdiv:  # some entries are missing a running time
                        timer = next(timerdiv.stripped_strings)
                    remove_url = list_item.find('div', class_='npo-asset-tile-delete')

                    if premium and not download_premium:
                        logger.debug('Skipping {}, no longer available without premium', title)
                        continue

                    entry_date = url.split('/')[-2]
                    entry_date = self._parse_date(entry_date)

                    if max_age >= 0 and date.today() - entry_date > timedelta(days=max_age):
                        logger.debug('Skipping {}, aired on {}', title, entry_date)
                        continue

                    e = Entry(series_info)
                    e['url'] = url
                    e['title'] = title
                    e['series_name'] = series_info['npo_name']
                    e['series_name_plain'] = self._convert_plain(series_info['npo_name'])
                    e['series_date'] = entry_date
                    e['series_id_type'] = 'date'
                    e['npo_id'] = episode_id
                    e['npo_premium'] = premium
                    e['npo_runtime'] = timer.strip('min').strip()
                    e['language'] = series_info['npo_language']

                    if remove_url and remove_url['data-link']:
                        e['remove_url'] = remove_url['data-link']
                        if config.get('remove_accepted'):
                            e.on_complete(self.entry_complete, task=task)
                    entries.append(e)

        return entries

    def on_task_input(self, task, config):
        # On https://www.npostart.nl/account-profile get the value for the profileId that is in use
        # Details of this account you can get at: https://www.npostart.nl/api/account/@me
        account_profile_url = 'https://www.npostart.nl/account-profile'

        email = config.get('email')
        logger.verbose('Retrieving NPOStart profiles for account {}', email)

        profilejson = self._get_page(task, config, account_profile_url).json()
        if 'profileId' not in profilejson:
            raise plugin.PluginError('Failed to fetch profile for NPO account')
        profileId = profilejson['profileId']
        entries = self._get_favourites_entries(task, config, profileId)
        return entries

    def entry_complete(self, e, task=None):
        if not e.accepted:
            logger.warning('Not removing {} entry {}', e.state, e['title'])
        elif 'remove_url' not in e:
            logger.warning('No remove_url for {}, skipping', e['title'])
        elif task.options.test:
            logger.info('Would remove from watchlist: {}', e['title'])
        else:
            logger.info('Removing from watchlist: {}', e['title'])

            headers = {
                'Origin': 'https://www.npostart.nl',
                'Referer': 'https://www.npostart.nl/mijn_npo',
                'X-XSRF-TOKEN': requests.cookies['XSRF-TOKEN'],
                'X-Requested-With': 'XMLHttpRequest',
            }

            try:
                delete_response = requests.post(
                    e['remove_url'], headers=headers, cookies=requests.cookies
                )
            except HTTPError as error:
                logger.error(
                    'Failed to remove {}, got status {}', e['title'], error.response.status_code
                )
            else:
                if delete_response.status_code != requests.codes.ok:
                    logger.warning(
                        'Failed to remove {}, got status {}',
                        e['title'],
                        delete_response.status_code,
                    )


@event('plugin.register')
def register_plugin():
    plugin.register(NPOWatchlist, 'npo_watchlist', api_ver=2, interfaces=['task'])
