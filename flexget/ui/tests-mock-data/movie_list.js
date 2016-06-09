var mockMovieListData = (function () {
	return {
		getMovieLists: getMovieLists,
		getMovieListById: getMovieListById,
		getMovieListMovies: getMovieListMovies,
		getMovieListMovieById: getMovieListMovieById,
		createMovieList: createMovieList
	};

	function getMovieLists() {
		return {
			"movie_lists": [
				{
					"added_on": "Mon, 11 Apr 2016 09:32:42 GMT",
					"id": 1,
					"name": "Looking"
				},
				{
					"added_on": "Tue, 12 Apr 2016 21:23:11 GMT",
					"id": 2,
					"name": "Downloaded Movies"
				}
			]
		}
	}

	function getMovieListById() {
		return {
			"added_on": "Mon, 11 Apr 2016 09:32:42 GMT",
			"id": 1,
			"name": "Looking"
		}
	}

	function getMovieListMovies() {
		return {
			"movies": [
				{
					"added_on": "Fri, 22 Apr 2016 09:06:42 GMT",
					"id": 178,
					"list_id": 1,
					"movies_list_ids": [
						{
							"added_on": "Fri, 22 Apr 2016 09:06:42 GMT",
							"id": 529,
							"id_name": "imdb_id",
							"id_value": "tt1700841",
							"movie_id": 178
						},
						{
							"added_on": "Fri, 22 Apr 2016 09:06:42 GMT",
							"id": 530,
							"id_name": "trakt_movie_id",
							"id_value": "137261",
							"movie_id": 178
						},
						{
							"added_on": "Fri, 22 Apr 2016 09:06:42 GMT",
							"id": 531,
							"id_name": "tmdb_id",
							"id_value": "223702",
							"movie_id": 178
						}
					],
					"title": "Sausage Party",
					"year": 2016
				},
				{
					"added_on": "Sat, 07 May 2016 10:53:10 GMT",
					"id": 205,
					"list_id": 1,
					"movies_list_ids": [
						{
							"added_on": "Sat, 07 May 2016 10:53:10 GMT",
							"id": 593,
							"id_name": "imdb_id",
							"id_value": "tt1913166",
							"movie_id": 205
						},
						{
							"added_on": "Sat, 07 May 2016 10:53:10 GMT",
							"id": 594,
							"id_name": "trakt_movie_id",
							"id_value": "58036",
							"movie_id": 205
						},
						{
							"added_on": "Sat, 07 May 2016 10:53:10 GMT",
							"id": 595,
							"id_name": "tmdb_id",
							"id_value": "78383",
							"movie_id": 205
						}
					],
					"title": "Nurse 3-D",
					"year": 2014
				},
				{
					"added_on": "Wed, 04 May 2016 09:07:14 GMT",
					"id": 189,
					"list_id": 1,
					"movies_list_ids": [
						{
							"added_on": "Wed, 04 May 2016 09:07:14 GMT",
							"id": 557,
							"id_name": "imdb_id",
							"id_value": "tt0077766",
							"movie_id": 189
						},
						{
							"added_on": "Wed, 04 May 2016 09:07:14 GMT",
							"id": 558,
							"id_name": "trakt_movie_id",
							"id_value": "458",
							"movie_id": 189
						},
						{
							"added_on": "Wed, 04 May 2016 09:07:14 GMT",
							"id": 559,
							"id_name": "tmdb_id",
							"id_value": "579",
							"movie_id": 189
						}
					],
					"title": "Jaws 2",
					"year": 1978
				},
				{
					"added_on": "Sat, 30 Apr 2016 09:06:49 GMT",
					"id": 186,
					"list_id": 1,
					"movies_list_ids": [
						{
							"added_on": "Sat, 30 Apr 2016 09:06:49 GMT",
							"id": 550,
							"id_name": "imdb_id",
							"id_value": "tt3072482",
							"movie_id": 186
						},
						{
							"added_on": "Sat, 30 Apr 2016 09:06:49 GMT",
							"id": 551,
							"id_name": "trakt_movie_id",
							"id_value": "221309",
							"movie_id": 186
						},
						{
							"added_on": "Sat, 30 Apr 2016 09:06:49 GMT",
							"id": 552,
							"id_name": "tmdb_id",
							"id_value": "325348",
							"movie_id": 186
						}
					],
					"title": "Hardcore Henry",
					"year": 2016
				}
			],
			"number_of_movies": 10,
			"page": 1,
			"total_number_of_movies": 27,
			"total_number_of_pages": 3
		}
	}

	function getMovieListMovieById() {
		return {
			"added_on": "Sat, 30 Apr 2016 09:06:49 GMT",
			"id": 186,
			"list_id": 1,
			"movies_list_ids": [
				{
					"added_on": "Sat, 30 Apr 2016 09:06:49 GMT",
					"id": 550,
					"id_name": "imdb_id",
					"id_value": "tt3072482",
					"movie_id": 186
				},
				{
					"added_on": "Sat, 30 Apr 2016 09:06:49 GMT",
					"id": 551,
					"id_name": "trakt_movie_id",
					"id_value": "221309",
					"movie_id": 186
				},
				{
					"added_on": "Sat, 30 Apr 2016 09:06:49 GMT",
					"id": 552,
					"id_name": "tmdb_id",
					"id_value": "325348",
					"movie_id": 186
				}
			],
			"title": "Hardcore Henry",
			"year": 2016
		}
	}
	
	function createMovieList() {
		return {
			"added_on": "Mon, 09 Jun 2016 09:32:42 GMT",
			"id": 33,
			"name": "New List"
		}
	}
})();