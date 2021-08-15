from unicodedata import normalize
import re

SCHEMA_SERVER = {
    'oneOf': [
        {
            'type': 'object',
            'properties': {
                'host': {'type': 'string', "default": "http://localhost:8096"},
                "username": {'type': 'string'},
                "password": {'type': 'string'},
                "return_host": {'type': 'string', 'enum': ['lan', 'wan']},
            },
            'required': ['username', "password"],
            'additionalProperties': False,
        },
        {
            'type': 'object',
            'properties': {
                'host': {'type': 'string', "default": "http://localhost:8096"},
                'username': {'type': 'string'},
                "apikey": {'type': 'string'},
                "return_host": {'type': 'string', 'enum': ['lan', 'wan']},
            },
            'required': ['username', 'apikey'],
            'additionalProperties': False,
        },
    ]
}


SCHEMA_SERVER_TAG = {"server": {**SCHEMA_SERVER}}


SORT_FIELDS = [
    'comunity_rating',
    'critic_rating',
    'date_created',
    'date_played',
    'play_count',
    'premiere_date',
    'production_year',
    'sort_name',
    'random',
    'revenue',
    'runtime',
]


field_map = {
    'media': {
        'emby_id': 'id',
        'emby_name': 'name',
        'emby_fullname': 'fullname',
        'emby_type': 'mtype',
        'emby_created_date': 'created_date',
        'emby_path': 'path',
        'emby_filename': 'filename',
        'emby_file_extension': 'file_extension',
        'emby_watched': 'watched',
        'emby_favorite': 'favorite',
        'emby_playcount': 'playcount',
        'emby_media_sources_raw': 'media_sources_raw',
        'emby_format_3d': 'format_3d',
        'emby_audio': 'audio',
        'emby_quality': 'quality',
        'emby_subtitles': 'subtitles',
        'imdb_url': 'imdb_url',
        'emby_download_url': 'download_url',
        'emby_library_name': 'library_name',
        'emby_page': 'page',
    },
    'series': {
        'emby_serie_year': 'serie_year',
        'emby_serie_aired_date': 'serie_aired_date',
        'emby_serie_id': 'serie_id',
        'emby_serie_name': 'serie_name',
        'emby_serie_photo': 'serie_photo',
        'emby_serie_imdb_id': 'serie_imdb_id',
        'emby_serie_tvdb_id': 'serie_tvdb_id',
        'emby_serie_overview': 'serie_overview',
        'emby_serie_page': 'serie_page',
        'imdb_id': 'serie_imdb_id',
        'tvdb_id': 'serie_tvdb_id',
    },
    'season': {
        'emby_season': 'season',
        'emby_season_name': 'season_name',
        'emby_season_id': 'season_id',
        'emby_season_page': 'season_page',
        'emby_season_photo': 'season_photo',
        'emby_season_imdb_id': 'season_imdb_id',
        'emby_season_tmdb_id': 'season_tmdb_id',
        'emby_season_tvdb_id': 'season_tvdb_id',
    },
    'episode': {
        'emby_episode': 'episode',
        'emby_ep_name': 'ep_name',
        'emby_ep_page': 'ep_page',
        'emby_ep_id': 'ep_id',
        'emby_ep_photo': 'ep_photo',
        'emby_ep_imdb_id': 'ep_imdb_id',
        'emby_ep_tmdb_id': 'ep_tmdb_id',
        'emby_ep_tvdb_id': 'ep_tvdb_id',
        'emby_ep_aired_date': 'ep_aired_date',
        'emby_ep_overview': 'ep_overview',
    },
    'movie': {
        'movie_name': 'movie_name',
        'movie_year': 'movie_year',
        'emby_movie_name': 'movie_name',
        'emby_movie_id': 'movie_id',
        'emby_movie_imdb_id': 'movie_imdb_id',
        'emby_movie_tmdb_id': 'movie_tmdb_id',
        'emby_movie_year': 'movie_year',
        'emby_movie_aired_date': 'movie_aired_date',
        'emby_movie_photo': 'movie_photo',
        'emby_movie_page': 'movie_page',
        'emby_movie_overview': 'movie_overview',
        'imdb_id': 'movie_imdb_id',
        'tmdb_id': 'movie_tmdb_id',
    },
}


def simplify_text(text: str) -> str:
    """ Siplify text """

    if not isinstance(text, str):
        return text

    # Replace accented chars by their 'normal' couterparts
    result = normalize('NFKD', text)

    # Symbols that should be converted to white space
    result = re.sub(r'[ \(\)\-_\[\]\.]+', ' ', result)
    # Leftovers
    result = re.sub(r"[^a-zA-Z0-9 ]", "", result)
    # Replace multiple white spaces with one
    result = ' '.join(result.split())


def get_field_map(**kwargs):
    lazy_fields = field_map['media']

    media_type = kwargs.get('media_type')
    if not media_type:
        media_type = kwargs.get('emby_type', '')

    media_type = media_type.lower()

    if media_type in field_map:
        lazy_fields = {**lazy_fields, **field_map[media_type]}
    else:
        lazy_fields = {**lazy_fields, **field_map['movie']}

    if media_type == 'episode':
        lazy_fields = {**lazy_fields, **field_map['series'], **field_map['season']}
    elif media_type == 'season':
        lazy_fields = {**lazy_fields, **field_map['series']}

    return lazy_fields
