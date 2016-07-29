/* eslint-disable no-unused-vars */
var mockMovieListData = (function () {
	return {
		getMovieLists: getMovieLists,
		getMovieListById: getMovieListById,
		getMovieListMovies: getMovieListMovies,
		getMovieListMovieById: getMovieListMovieById,
		createMovieList: createMovieList,
		getMovieMetadata: getMovieMetadata
	};

	function getMovieLists() {
		return {
			'movie_lists': [
				{
					'added_on': 'Mon, 11 Apr 2016 09:32:42 GMT',
					'id': 1,
					'name': 'Looking'
				},
				{
					'added_on': 'Tue, 12 Apr 2016 21:23:11 GMT',
					'id': 2,
					'name': 'Downloaded Movies'
				}
			]
		};
	}

	function getMovieListById() {
		return {
			'added_on': 'Mon, 11 Apr 2016 09:32:42 GMT',
			'id': 1,
			'name': 'Looking'
		};
	}

	function getMovieListMovies() {
		return {
			'movies': [
				{
					'added_on': 'Fri, 22 Apr 2016 09:06:42 GMT',
					'id': 178,
					'list_id': 1,
					'movies_list_ids': [
						{
							'added_on': 'Fri, 22 Apr 2016 09:06:42 GMT',
							'id': 529,
							'id_name': 'imdb_id',
							'id_value': 'tt1700841',
							'movie_id': 178
						},
						{
							'added_on': 'Fri, 22 Apr 2016 09:06:42 GMT',
							'id': 530,
							'id_name': 'trakt_movie_id',
							'id_value': '137261',
							'movie_id': 178
						},
						{
							'added_on': 'Fri, 22 Apr 2016 09:06:42 GMT',
							'id': 531,
							'id_name': 'tmdb_id',
							'id_value': '223702',
							'movie_id': 178
						}
					],
					'title': 'Sausage Party',
					'year': 2016
				},
				{
					'added_on': 'Sat, 07 May 2016 10:53:10 GMT',
					'id': 205,
					'list_id': 1,
					'movies_list_ids': [
						{
							'added_on': 'Sat, 07 May 2016 10:53:10 GMT',
							'id': 593,
							'id_name': 'imdb_id',
							'id_value': 'tt1913166',
							'movie_id': 205
						},
						{
							'added_on': 'Sat, 07 May 2016 10:53:10 GMT',
							'id': 594,
							'id_name': 'trakt_movie_id',
							'id_value': '58036',
							'movie_id': 205
						},
						{
							'added_on': 'Sat, 07 May 2016 10:53:10 GMT',
							'id': 595,
							'id_name': 'tmdb_id',
							'id_value': '78383',
							'movie_id': 205
						}
					],
					'title': 'Nurse 3-D',
					'year': 2014
				},
				{
					'added_on': 'Wed, 04 May 2016 09:07:14 GMT',
					'id': 189,
					'list_id': 1,
					'movies_list_ids': [
						{
							'added_on': 'Wed, 04 May 2016 09:07:14 GMT',
							'id': 557,
							'id_name': 'imdb_id',
							'id_value': 'tt0077766',
							'movie_id': 189
						},
						{
							'added_on': 'Wed, 04 May 2016 09:07:14 GMT',
							'id': 558,
							'id_name': 'trakt_movie_id',
							'id_value': '458',
							'movie_id': 189
						},
						{
							'added_on': 'Wed, 04 May 2016 09:07:14 GMT',
							'id': 559,
							'id_name': 'tmdb_id',
							'id_value': '579',
							'movie_id': 189
						}
					],
					'title': 'Jaws 2',
					'year': 1978
				},
				{
					'added_on': 'Sat, 30 Apr 2016 09:06:49 GMT',
					'id': 186,
					'list_id': 1,
					'movies_list_ids': [
						{
							'added_on': 'Sat, 30 Apr 2016 09:06:49 GMT',
							'id': 550,
							'id_name': 'imdb_id',
							'id_value': 'tt3072482',
							'movie_id': 186
						},
						{
							'added_on': 'Sat, 30 Apr 2016 09:06:49 GMT',
							'id': 551,
							'id_name': 'trakt_movie_id',
							'id_value': '221309',
							'movie_id': 186
						},
						{
							'added_on': 'Sat, 30 Apr 2016 09:06:49 GMT',
							'id': 552,
							'id_name': 'tmdb_id',
							'id_value': '325348',
							'movie_id': 186
						}
					],
					'title': 'Hardcore Henry',
					'year': 2016
				}
			],
			'number_of_movies': 10,
			'page': 1,
			'total_number_of_movies': 27,
			'total_number_of_pages': 3
		};
	}

	function getMovieListMovieById() {
		return {
			'added_on': 'Sat, 30 Apr 2016 09:06:49 GMT',
			'id': 186,
			'list_id': 1,
			'movies_list_ids': [
				{
					'added_on': 'Sat, 30 Apr 2016 09:06:49 GMT',
					'id': 550,
					'id_name': 'imdb_id',
					'id_value': 'tt3072482',
					'movie_id': 186
				},
				{
					'added_on': 'Sat, 30 Apr 2016 09:06:49 GMT',
					'id': 551,
					'id_name': 'trakt_movie_id',
					'id_value': '221309',
					'movie_id': 186
				},
				{
					'added_on': 'Sat, 30 Apr 2016 09:06:49 GMT',
					'id': 552,
					'id_name': 'tmdb_id',
					'id_value': '325348',
					'movie_id': 186
				}
			],
			'title': 'Hardcore Henry',
			'year': 2016
		};
	}

	function createMovieList() {
		return {
			'added_on': 'Mon, 09 Jun 2016 09:32:42 GMT',
			'id': 33,
			'name': 'New List'
		};
	}

	function getMovieMetadata() {
		return {
			'cached_at': 'Thu, 09 Jun 2016 21:22:10 GMT',
			'genres': [
				'action',
				'adventure',
				'fantasy'
			],
			'homepage': 'http://www.warcraft-themovie.com/',
			'id': 50145,
			'images': {
				'banner': {
					'full': 'https://walter.trakt.us/images/movies/000/050/145/banners/original/186ef347c8.jpg'
				},
				'clearart': {
					'full': 'https://walter.trakt.us/images/movies/000/050/145/cleararts/original/8ee8691096.png'
				},
				'fanart': {
					'full': 'https://walter.trakt.us/images/movies/000/050/145/fanarts/original/e8785015d5.jpg',
					'medium': 'https://walter.trakt.us/images/movies/000/050/145/fanarts/medium/e8785015d5.jpg',
					'thumb': 'https://walter.trakt.us/images/movies/000/050/145/fanarts/thumb/e8785015d5.jpg'
				},
				'logo': {
					'full': 'https://walter.trakt.us/images/movies/000/050/145/logos/original/41c3ac6bad.png'
				},
				'poster': {
					'full': 'https://walter.trakt.us/images/movies/000/050/145/posters/original/f327360575.jpg',
					'medium': 'https://walter.trakt.us/images/movies/000/050/145/posters/medium/f327360575.jpg',
					'thumb': 'https://walter.trakt.us/images/movies/000/050/145/posters/thumb/f327360575.jpg'
				},
				'thumb': {
					'full': 'https://walter.trakt.us/images/movies/000/050/145/thumbs/original/017439146d.jpg'
				}
			},
			'imdb_id': 'tt0803096',
			'language': 'en',
			'overview': 'The peaceful realm of Azeroth stands on the brink of war as its civilization faces a fearsome race of invaders: orc warriors fleeing their dying home to colonize another. As a portal opens to connect the two worlds, one army faces destruction and the other faces extinction. From opposing sides, two heroes are set on a collision course that will decide the fate of their family, their people, and their home.',
			'rating': 7.36667,
			'released': null,
			'runtime': 123,
			'slug': 'warcraft-2016',
			'tagline': 'Two worlds. One home.',
			'title': 'Warcraft',
			'tmdb_id': 68735,
			'trailer': 'http://youtube.com/watch?v=2Rxoz13Bthc',
			'updated_at': 'Sun, 05 Jun 2016 08:51:15 GMT',
			'votes': 330,
			'year': 2016
		};
	}
}());