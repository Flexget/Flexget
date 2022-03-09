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
        'jellyfin_id': 'id',
        'jellyfin_name': 'name',
        'jellyfin_fullname': 'fullname',
        'jellyfin_type': 'mtype',
        'jellyfin_created_date': 'created_date',
        'jellyfin_path': 'path',
        'jellyfin_filename': 'filename',
        'jellyfin_file_extension': 'file_extension',
        'jellyfin_watched': 'watched',
        'jellyfin_favorite': 'favorite',
        'jellyfin_playcount': 'playcount',
        'jellyfin_media_sources_raw': 'media_sources_raw',
        'jellyfin_format_3d': 'format_3d',
        'jellyfin_audio': 'audio',
        'jellyfin_quality': 'quality',
        'jellyfin_subtitles': 'subtitles',
        'imdb_url': 'imdb_url',
        'jellyfin_download_url': 'download_url',
        'jellyfin_library_name': 'library_name',
        'jellyfin_page': 'page',
    },
    'series': {
        'jellyfin_serie_year': 'serie_year',
        'jellyfin_serie_aired_date': 'serie_aired_date',
        'jellyfin_serie_id': 'serie_id',
        'jellyfin_serie_name': 'serie_name',
        'jellyfin_serie_photo': 'serie_photo',
        'jellyfin_serie_imdb_id': 'serie_imdb_id',
        'jellyfin_serie_tvdb_id': 'serie_tvdb_id',
        'jellyfin_serie_overview': 'serie_overview',
        'jellyfin_serie_page': 'serie_page',
        'imdb_id': 'serie_imdb_id',
        'tvdb_id': 'serie_tvdb_id',
    },
    'season': {
        'jellyfin_season': 'season',
        'jellyfin_season_name': 'season_name',
        'jellyfin_season_id': 'season_id',
        'jellyfin_season_page': 'season_page',
        'jellyfin_season_photo': 'season_photo',
        'jellyfin_season_imdb_id': 'season_imdb_id',
        'jellyfin_season_tmdb_id': 'season_tmdb_id',
        'jellyfin_season_tvdb_id': 'season_tvdb_id',
    },
    'episode': {
        'jellyfin_episode': 'episode',
        'jellyfin_ep_name': 'ep_name',
        'jellyfin_ep_page': 'ep_page',
        'jellyfin_ep_id': 'ep_id',
        'jellyfin_ep_photo': 'ep_photo',
        'jellyfin_ep_imdb_id': 'ep_imdb_id',
        'jellyfin_ep_tmdb_id': 'ep_tmdb_id',
        'jellyfin_ep_tvdb_id': 'ep_tvdb_id',
        'jellyfin_ep_aired_date': 'ep_aired_date',
        'jellyfin_ep_overview': 'ep_overview',
    },
    'movie': {
        'movie_name': 'movie_name',
        'movie_year': 'movie_year',
        'jellyfin_movie_name': 'movie_name',
        'jellyfin_movie_id': 'movie_id',
        'jellyfin_movie_imdb_id': 'movie_imdb_id',
        'jellyfin_movie_tmdb_id': 'movie_tmdb_id',
        'jellyfin_movie_year': 'movie_year',
        'jellyfin_movie_aired_date': 'movie_aired_date',
        'jellyfin_movie_photo': 'movie_photo',
        'jellyfin_movie_page': 'movie_page',
        'jellyfin_movie_overview': 'movie_overview',
        'imdb_id': 'movie_imdb_id',
        'tmdb_id': 'movie_tmdb_id',
    },
}


def get_field_map(**kwargs):
    lazy_fields = field_map['media']

    media_type = kwargs.get('media_type')
    if not media_type:
        media_type = kwargs.get('jellyfin_type', '')

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
