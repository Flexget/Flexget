# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
from past.builtins import cmp
from builtins import *  # pylint: disable=unused-import, redefined-builtin
import pytest

from flexget.utils import json


def clean_attributes(data):
    """
    Removes non constant attributes from response since they can change and will trigger a fail
    :param data: Original response json
    :return: Response json without non constant attributes
    """
    data.pop('cached_at')
    data.pop('votes')
    data.pop('updated_at')
    data.pop('rating')
    data.pop('status', None)
    data.pop('number_of_aired_episodes', None)
    return data


@pytest.mark.online
class TestTraktSeriesLookupAPI(object):
    config = 'tasks: {}'

    def test_trakt_series_lookup_no_params(self, api_client):
        # Bad API call
        rsp = api_client.get('/trakt/series/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        expected_payload = {
            "air_day": "Monday",
            "air_time": "20:00",
            "certification": "TV-14",
            "country": "us",
            "first_aired": "Fri, 10 Sep 1993 07:00:00 GMT",
            "genres": [
                "drama",
                "mystery",
                "science fiction",
                "fantasy"
            ],
            "homepage": "http://www.fox.com/the-x-files",
            "id": 4063,
            "images": {
                "banner": {
                    "full": "https://walter.trakt.us/images/shows/000/004/063/banners/original/0927751ec8.jpg"
                },
                "clearart": {
                    "full": "https://walter.trakt.us/images/shows/000/004/063/cleararts/original/a4a0db2c8d.png"
                },
                "fanart": {
                    "full": "https://walter.trakt.us/images/shows/000/004/063/fanarts/original/1f0b461052.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/004/063/fanarts/medium/1f0b461052.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/004/063/fanarts/thumb/1f0b461052.jpg"
                },
                "logo": {
                    "full": "https://walter.trakt.us/images/shows/000/004/063/logos/original/ba7ac727c2.png"
                },
                "poster": {
                    "full": "https://walter.trakt.us/images/shows/000/004/063/posters/original/034cc070a9.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/004/063/posters/medium/034cc070a9.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/004/063/posters/thumb/034cc070a9.jpg"
                },
                "thumb": {
                    "full": "https://walter.trakt.us/images/shows/000/004/063/thumbs/original/74d4f3d798.jpg"
                }
            },
            "imdb_id": "tt0106179",
            "language": "en",
            "network": "FOX (US)",
            "overview": "The X-Files focused on the exploits of FBI Agents Fox Mulder, Dana Scully, John Doggett and Monica Reyes and their investigations into the paranormal. From genetic mutants and killer insects to a global conspiracy concerning the colonization of Earth by an alien species, this mind-boggling, humorous and occasionally frightening series created by Chris Carter has been one of the world's most popular sci-fi/drama shows since its humble beginnings in 1993.",
            "runtime": 45,
            "slug": "the-x-files",
            "timezone": "America/New_York",
            "title": "The X-Files",
            "tmdb_id": 4087,
            "tvdb_id": 77398,
            "tvrage_id": 6312,
            "year": 1993
        }

        rsp = api_client.get('/trakt/series/the x-files/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_year_param(self, api_client):
        expected_payload = {
            "air_day": "Tuesday",
            "air_time": "20:00",
            "certification": "TV-PG",
            "country": "us",
            "first_aired": "Fri, 21 Sep 1990 00:00:00 GMT",
            "genres": [
                "drama",
                "action",
                "crime",
                "fantasy"
            ],
            "homepage": None,
            "id": 235,
            "images": {
                "banner": {
                    "full": "https://walter.trakt.us/images/shows/000/000/235/banners/original/7269414ca0.jpg"
                },
                "clearart": {
                    "full": None
                },
                "fanart": {
                    "full": "https://walter.trakt.us/images/shows/000/000/235/fanarts/original/826b9ef114.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/000/235/fanarts/medium/826b9ef114.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/000/235/fanarts/thumb/826b9ef114.jpg"
                },
                "logo": {
                    "full": "https://walter.trakt.us/images/shows/000/000/235/logos/original/d31e38d6d4.png"
                },
                "poster": {
                    "full": "https://walter.trakt.us/images/shows/000/000/235/posters/original/fb1d03e09f.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/000/235/posters/medium/fb1d03e09f.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/000/235/posters/thumb/fb1d03e09f.jpg"
                },
                "thumb": {
                    "full": "https://walter.trakt.us/images/shows/000/000/235/thumbs/original/407d93ca8b.jpg"
                }
            },
            "imdb_id": "tt0098798",
            "language": "en",
            "network": "CBS",
            "overview": "Central City Police forensic scientist Barry Allen's crime lab is struck by lightning. Allen's electrified body is flung into and shatters a cabinet of chemicals, which are both electrified and forced to interact with each other and with his physiology when they come into physical contact with his body. He soon discovers that the accident has changed his body's metabolism and as a result he has gained the ability to move at superhuman speed. Barry Allen has become the Flash.",
            "runtime": 45,
            "slug": "the-flash",
            "timezone": "America/New_York",
            "title": "The Flash",
            "tmdb_id": 236,
            "tvdb_id": 78650,
            "tvrage_id": 5781,
            "year": 1990
        }

        rsp = api_client.get('/trakt/series/the flash/?year=1990')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_trakt_slug_id_param(self, api_client):
        expected_payload = {
            "air_day": "Saturday",
            "air_time": None,
            "certification": None,
            "country": None,
            "first_aired": "Sat, 11 Nov 1967 00:00:00 GMT",
            "genres": [
                "animation"
            ],
            "homepage": None,
            "id": 75481,
            "images": {
                "banner": {
                    "full": None
                },
                "clearart": {
                    "full": None
                },
                "fanart": {
                    "full": None,
                    "medium": None,
                    "thumb": None
                },
                "logo": {
                    "full": None
                },
                "poster": {
                    "full": "https://walter.trakt.us/images/shows/000/075/481/posters/original/0782d34337.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/075/481/posters/medium/0782d34337.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/075/481/posters/thumb/0782d34337.jpg"
                },
                "thumb": {
                    "full": None
                }
            },
            "imdb_id": None,
            "language": None,
            "network": "CBS",
            "overview": "The Flash is- of course!- the fastest man alive. Barry Allen, otherwise known as the Flash, and his sidekick Wally West, otherwise known as Kid Flash, battle evil villains and aliens who try to cause mayhem on Earth. They can outrun a bullet, vibrate through solid walls, and do all sorts of other things with their incredible speed. When there is trouble, Barry and Wally open up their rings which shoot out their costumes.",
            "runtime": 7,
            "slug": "the-flash-1967",
            "timezone": "Europe/London",
            "title": "The Flash",
            "tmdb_id": None,
            "tvdb_id": 272094,
            "tvrage_id": None,
            "year": 1967
        }

        rsp = api_client.get('/trakt/series/the flash/?trakt_slug=the-flash-1967')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_tmdb_id_param(self, api_client):
        expected_payload = {
            "air_day": "Tuesday",
            "air_time": "20:00",
            "certification": "TV-14",
            "country": "us",
            "first_aired": "Tue, 07 Oct 2014 07:00:00 GMT",
            "genres": [
                "drama",
                "fantasy",
                "science fiction",
                "action",
                "adventure"
            ],
            "homepage": "http://www.cwtv.com/shows/the-flash/",
            "id": 60300,
            "images": {
                "banner": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/banners/original/b2c305a2dc.jpg"
                },
                "clearart": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/cleararts/original/660e6efe67.png"
                },
                "fanart": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/fanarts/original/df36c9a731.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/060/300/fanarts/medium/df36c9a731.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/060/300/fanarts/thumb/df36c9a731.jpg"
                },
                "logo": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/logos/original/ab151d1043.png"
                },
                "poster": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/posters/original/79bd96a4d3.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/060/300/posters/medium/79bd96a4d3.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/060/300/posters/thumb/79bd96a4d3.jpg"
                },
                "thumb": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/thumbs/original/eab955a39c.jpg"
                }
            },
            "imdb_id": "tt3107288",
            "language": "en",
            "network": "The CW",
            "overview": "After a particle accelerator causes a freak storm, CSI Investigator Barry Allen is struck by lightning and falls into a coma. Months later he awakens with the power of super speed, granting him the ability to move through Central City like an unseen guardian angel. Though initially excited by his newfound powers, Barry is shocked to discover he is not the only \"meta-human\" who was created in the wake of the accelerator explosion – and not everyone is using their new powers for good. Barry partners with S.T.A.R. Labs and dedicates his life to protect the innocent. For now, only a few close friends and associates know that Barry is literally the fastest man alive, but it won't be long before the world learns what Barry Allen has become... The Flash.",
            "runtime": 45,
            "slug": "the-flash-2014",
            "timezone": "America/New_York",
            "title": "The Flash",
            "tmdb_id": 60735,
            "tvdb_id": 279121,
            "tvrage_id": 36939,
            "year": 2014
        }

        rsp = api_client.get('/trakt/series/the flash/?tmdb_id=60735')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_imdb_id_param(self, api_client):
        expected_payload = {
            "air_day": "Tuesday",
            "air_time": "20:00",
            "certification": "TV-14",
            "country": "us",
            "first_aired": "Tue, 07 Oct 2014 07:00:00 GMT",
            "genres": [
                "drama",
                "fantasy",
                "science fiction",
                "action",
                "adventure"
            ],
            "homepage": "http://www.cwtv.com/shows/the-flash/",
            "id": 60300,
            "images": {
                "banner": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/banners/original/b2c305a2dc.jpg"
                },
                "clearart": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/cleararts/original/660e6efe67.png"
                },
                "fanart": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/fanarts/original/df36c9a731.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/060/300/fanarts/medium/df36c9a731.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/060/300/fanarts/thumb/df36c9a731.jpg"
                },
                "logo": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/logos/original/ab151d1043.png"
                },
                "poster": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/posters/original/79bd96a4d3.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/060/300/posters/medium/79bd96a4d3.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/060/300/posters/thumb/79bd96a4d3.jpg"
                },
                "thumb": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/thumbs/original/eab955a39c.jpg"
                }
            },
            "imdb_id": "tt3107288",
            "language": "en",
            "network": "The CW",
            "overview": "After a particle accelerator causes a freak storm, CSI Investigator Barry Allen is struck by lightning and falls into a coma. Months later he awakens with the power of super speed, granting him the ability to move through Central City like an unseen guardian angel. Though initially excited by his newfound powers, Barry is shocked to discover he is not the only \"meta-human\" who was created in the wake of the accelerator explosion – and not everyone is using their new powers for good. Barry partners with S.T.A.R. Labs and dedicates his life to protect the innocent. For now, only a few close friends and associates know that Barry is literally the fastest man alive, but it won't be long before the world learns what Barry Allen has become... The Flash.",
            "runtime": 45,
            "slug": "the-flash-2014",
            "timezone": "America/New_York",
            "title": "The Flash",
            "tmdb_id": 60735,
            "tvdb_id": 279121,
            "tvrage_id": 36939,
            "year": 2014
        }

        rsp = api_client.get('/trakt/series/the flash/?imdb_id=tt3107288')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_tvdb_id_param(self, api_client):
        expected_payload = {
            "air_day": "Tuesday",
            "air_time": "20:00",
            "certification": "TV-14",
            "country": "us",
            "first_aired": "Tue, 07 Oct 2014 07:00:00 GMT",
            "genres": [
                "drama",
                "fantasy",
                "science fiction",
                "action",
                "adventure"
            ],
            "homepage": "http://www.cwtv.com/shows/the-flash/",
            "id": 60300,
            "images": {
                "banner": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/banners/original/b2c305a2dc.jpg"
                },
                "clearart": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/cleararts/original/660e6efe67.png"
                },
                "fanart": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/fanarts/original/df36c9a731.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/060/300/fanarts/medium/df36c9a731.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/060/300/fanarts/thumb/df36c9a731.jpg"
                },
                "logo": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/logos/original/ab151d1043.png"
                },
                "poster": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/posters/original/79bd96a4d3.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/060/300/posters/medium/79bd96a4d3.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/060/300/posters/thumb/79bd96a4d3.jpg"
                },
                "thumb": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/thumbs/original/eab955a39c.jpg"
                }
            },
            "imdb_id": "tt3107288",
            "language": "en",
            "network": "The CW",
            "overview": "After a particle accelerator causes a freak storm, CSI Investigator Barry Allen is struck by lightning and falls into a coma. Months later he awakens with the power of super speed, granting him the ability to move through Central City like an unseen guardian angel. Though initially excited by his newfound powers, Barry is shocked to discover he is not the only \"meta-human\" who was created in the wake of the accelerator explosion – and not everyone is using their new powers for good. Barry partners with S.T.A.R. Labs and dedicates his life to protect the innocent. For now, only a few close friends and associates know that Barry is literally the fastest man alive, but it won't be long before the world learns what Barry Allen has become... The Flash.",
            "runtime": 45,
            "slug": "the-flash-2014",
            "timezone": "America/New_York",
            "title": "The Flash",
            "tmdb_id": 60735,
            "tvdb_id": 279121,
            "tvrage_id": 36939,
            "year": 2014
        }

        rsp = api_client.get('/trakt/series/the flash/?tvdb_id=279121')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_tvrage_id_param(self, api_client):
        expected_payload = {
            "air_day": "Tuesday",
            "air_time": "20:00",
            "certification": "TV-14",
            "country": "us",
            "first_aired": "Tue, 07 Oct 2014 07:00:00 GMT",
            "genres": [
                "drama",
                "fantasy",
                "science fiction",
                "action",
                "adventure"
            ],
            "homepage": "http://www.cwtv.com/shows/the-flash/",
            "id": 60300,
            "images": {
                "banner": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/banners/original/b2c305a2dc.jpg"
                },
                "clearart": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/cleararts/original/660e6efe67.png"
                },
                "fanart": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/fanarts/original/df36c9a731.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/060/300/fanarts/medium/df36c9a731.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/060/300/fanarts/thumb/df36c9a731.jpg"
                },
                "logo": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/logos/original/ab151d1043.png"
                },
                "poster": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/posters/original/79bd96a4d3.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/060/300/posters/medium/79bd96a4d3.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/060/300/posters/thumb/79bd96a4d3.jpg"
                },
                "thumb": {
                    "full": "https://walter.trakt.us/images/shows/000/060/300/thumbs/original/eab955a39c.jpg"
                }
            },
            "imdb_id": "tt3107288",
            "language": "en",
            "network": "The CW",
            "overview": "After a particle accelerator causes a freak storm, CSI Investigator Barry Allen is struck by lightning and falls into a coma. Months later he awakens with the power of super speed, granting him the ability to move through Central City like an unseen guardian angel. Though initially excited by his newfound powers, Barry is shocked to discover he is not the only \"meta-human\" who was created in the wake of the accelerator explosion – and not everyone is using their new powers for good. Barry partners with S.T.A.R. Labs and dedicates his life to protect the innocent. For now, only a few close friends and associates know that Barry is literally the fastest man alive, but it won't be long before the world learns what Barry Allen has become... The Flash.",
            "runtime": 45,
            "slug": "the-flash-2014",
            "timezone": "America/New_York",
            "title": "The Flash",
            "tmdb_id": 60735,
            "tvdb_id": 279121,
            "tvrage_id": 36939,
            "year": 2014
        }

        rsp = api_client.get('/trakt/series/the flash/?tvrage_id=36939')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_trakt_id_param(self, api_client):
        expected_payload = {
            "air_day": "Saturday",
            "air_time": None,
            "certification": None,
            "country": None,
            "first_aired": "Sat, 11 Nov 1967 08:00:00 GMT",
            "genres": [
                "animation"
            ],
            "homepage": None,
            "id": 75481,
            "images": {
                "banner": {
                    "full": None
                },
                "clearart": {
                    "full": None
                },
                "fanart": {
                    "full": None,
                    "medium": None,
                    "thumb": None
                },
                "logo": {
                    "full": None
                },
                "poster": {
                    "full": "https://walter.trakt.us/images/shows/000/075/481/posters/original/0782d34337.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/075/481/posters/medium/0782d34337.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/075/481/posters/thumb/0782d34337.jpg"
                },
                "thumb": {
                    "full": None
                }
            },
            "imdb_id": None,
            "language": None,
            "network": "CBS",
            "overview": "The Flash is- of course!- the fastest man alive. Barry Allen, otherwise known as the Flash, and his sidekick Wally West, otherwise known as Kid Flash, battle evil villains and aliens who try to cause mayhem on Earth. They can outrun a bullet, vibrate through solid walls, and do all sorts of other things with their incredible speed. When there is trouble, Barry and Wally open up their rings which shoot out their costumes.",
            "runtime": 7,
            "slug": "the-flash-1967",
            "timezone": "Europe/London",
            "title": "The Flash",
            "tmdb_id": None,
            "tvdb_id": 272094,
            "tvrage_id": None,
            "year": 1967
        }

        rsp = api_client.get('/trakt/series/the flash/?trakt_id=75481')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_actors_param(self, api_client):
        expected_payload = {
            "actors": [{
                u'412714': {u'death': None, u'name': u'Mitch Pileggi', u'tmdb_id': u'12644',
                        u'trakt_slug': u'mitch-pileggi', u'imdb_id': u'nm0683379', u'trakt_id': 412714,
                        u'birthday': u'1952/04/05',
                        u'images': {u'fanart': {u'medium': None, u'full': None, u'thumb': None}, u'headshot': {
                            u'medium': u'https://walter.trakt.us/images/person_shows/000/180/191/headshots/medium/751e84197d.jpg',
                            u'full': u'https://walter.trakt.us/images/person_shows/000/180/191/headshots/original/751e84197d.jpg',
                            u'thumb': u'https://walter.trakt.us/images/person_shows/000/180/191/headshots/thumb/751e84197d.jpg'}},
                        u'homepage': u'',
                        u'biography': u'Mitchell Craig "Mitch" Pileggi (born April 5, 1952) is an American actor. Pileggi is known for playing FBI assistant director Walter Skinner on the long-running popular series The X-Files. He also had a recurring role on Stargate Atlantis as Col. Steven Caldwell. He appeared in the 2008 film, Flash of Genius.'},
                u'414777': {u'death': None, u'name': u'David Duchovny', u'tmdb_id': u'12640',
                        u'trakt_slug': u'david-duchovny', u'imdb_id': u'nm0000141', u'trakt_id': 414777,
                        u'birthday': u'1960/08/07', u'images': {u'fanart': {
                            u'medium': u'https://walter.trakt.us/images/person_shows/000/160/968/headshots/medium/7dbe745bf3.jpg',
                            u'full': u'https://walter.trakt.us/images/person_shows/000/160/968/headshots/original/7dbe745bf3.jpg',
                            u'thumb': u'https://walter.trakt.us/images/person_shows/000/160/968/headshots/thumb/7dbe745bf3.jpg'},
                            u'headshot': {
                                u'medium': u'https://walter.trakt.us/images/person_shows/000/160/968/headshots/medium/7dbe745bf3.jpg',
                                u'full': u'https://walter.trakt.us/images/person_shows/000/160/968/headshots/original/7dbe745bf3.jpg',
                                u'thumb': u'https://walter.trakt.us/images/person_shows/000/160/968/headshots/thumb/7dbe745bf3.jpg'}},
                        u'homepage': u'',
                        u'biography': u'David William Duchovny (born August 7, 1960, height 6\' 0\xbd" (1,84 m)) is an American actor, writer, and director. He is best known for playing Fox Mulder on The X-Files and Hank Moody on Californication, both of which have earned him Golden Globe awards  Duchovny was born in New York City, New York in 1960. He is the son of Margaret "Meg" (n\xe9e Miller), a school administrator and teacher, and Amram "Ami" Ducovny (1927\u20132003), a writer and publicist who worked for the American Jewish Committee. His father was Jewish, from a family that immigrated from the Russian Empire and Poland. His mother is a Lutheran emigrant from Aberdeen, Scotland. His father dropped the h in his last name to avoid the sort of mispronunciations he encountered while serving in the Army.\n\nDuchovny attended Grace Church School and The Collegiate School For Boys; both are in Manhattan. He graduated from Princeton University in 1982 with a B.A. in English Literature. He was a member of Charter Club, one of the university\'s eating clubs. In 1982, his poetry received an honorable mention for a college prize from the Academy of American Poets. The title of his senior thesis was The Schizophrenic Critique of Pure Reason in Beckett\'s Early Novels. Duchovny played a season of junior varsity basketball as a shooting guard and centerfield for the varsity baseball team.\n\nHe received a Master of Arts in English Literature from Yale University and subsequently began work on a Ph.D. that remains unfinished. The title of his uncompleted doctoral thesis was Magic and Technology in Contemporary Poetry and Prose. At Yale, he was a student of popular literary critic Harold Bloom.\n\nDuchovny married actress T\xe9a Leoni on May 6, 1997. In April 1999, Leoni gave birth to a daughter, Madelaine West Duchovny. Their second child, a son, Kyd Miller Duchovny, was born in June 2002. Duchovny is a former vegetarian and, as of 2007, is a pescetarian.\n\nOn August 28, 2008, Duchovny announced that he had checked himself into a rehabilitation facility for treating sex addiction. On October 15, 2008, Duchovny\'s and Leoni\'s representatives issued a statement revealing they had separated several months earlier.A week later, Duchovny\'s lawyer said that he planned to sue the Daily Mail over an article it ran that claimed he had an affair with Hungarian tennis instructor Edit Pakay while still married to Leoni, a claim that Duchovny has denied. On November 15, 2008, the Daily Mail retracted their claims. After getting back together, Duchovny and Leoni once again split on June 29, 2011.'},
                u'9295': {u'death': None, u'name': u'Gillian Anderson', u'tmdb_id': u'12214',
                      u'trakt_slug': u'gillian-anderson', u'imdb_id': u'nm0000096', u'trakt_id': 9295,
                      u'birthday': u'1968/08/09', u'images': {u'fanart': {
                        u'medium': u'https://walter.trakt.us/images/person_shows/000/160/967/headshots/medium/508bae4b25.jpg',
                        u'full': u'https://walter.trakt.us/images/person_shows/000/160/967/headshots/original/508bae4b25.jpg',
                        u'thumb': u'https://walter.trakt.us/images/person_shows/000/160/967/headshots/thumb/508bae4b25.jpg'},
                        u'headshot': {
                            u'medium': u'https://walter.trakt.us/images/person_shows/000/160/967/headshots/medium/508bae4b25.jpg',
                            u'full': u'https://walter.trakt.us/images/person_shows/000/160/967/headshots/original/508bae4b25.jpg',
                            u'thumb': u'https://walter.trakt.us/images/person_shows/000/160/967/headshots/thumb/508bae4b25.jpg'}},
                      u'homepage': u'',
                      u'biography': u'Gillian Leigh Anderson (born August 9, 1968, height 5\' 3" (1,60 m)) is an American actress. After beginning her career in theatre, Anderson achieved international recognition for her role as Special Agent Dana Scully on the American television series The X-Files. Her film work includes The House of Mirth (2000), The Mighty Celt (2005), The Last King of Scotland (2006), and two X-Files films, The X-Files (1998) and The X-Files: I Want to Believe (2008).\n\nAnderson was born in Chicago, Illinois, the daughter of Rosemary Anderson (n\xe9e Lane), a computer analyst, and Edward Anderson, who owned a film post-production company.Her father was of English descent, while her mother was of Irish and German ancestry. Soon after her birth, her family moved to Puerto Rico for 15 months; her family then moved to the United Kingdom where she lived until she was 11 years old. She lived for five years in Rosebery Gardens, Crouch End, London, and for 15 months in Albany Road, Stroud Green, London, so that her father could attend the London Film School.\n\nShe was a pupil of Coleridge Primary School. When Anderson was 11 years old, her family moved again, this time to Grand Rapids, Michigan. She attended Fountain Elementary and then City High-Middle School, a program for gifted students with a strong emphasis on the humanities; she graduated in 1986.\n\nAlong with other actors (notably Linda Thorson and John Barrowman) Anderson is bidialectal. With her English accent and background, Anderson was mocked and felt out of place in the American Midwest and soon adopted a Midwest accent. To this day, her accent depends on her location \u2014 for instance, in an interview with Jay Leno she spoke in an American accent, but shifted it for an interview with Michael Parkinson.\n\nAnderson was interested in marine biology, but began acting her freshman year in high school productions, and later in community theater, and served as a student intern at the Grand Rapids Civic Theatre &amp; School of Theatre Arts. She attended The Theatre School at DePaul University in Chicago (formerly the Goodman School of Drama), where she earned a Bachelor of Fine Arts in 1990. She also participated in the National Theatre of Great Britain\'s summer program at Cornell University.\n\nAnderson\'s brother died in 2011 of a brain tumor, at the age of 30.\n\nAnderson married her first husband, Clyde Klotz, The X-Files series assistant art director, on New Year\'s Day, 1994, in Hawaii in a Buddhist ceremony. They had a daughter, Piper Maru (born September 1994), for whom Chris Carter named the X-Files episode of the same name, and divorced in 1997.] In December 2004, Anderson married Julian Ozanne, a documentary filmmaker, on Lamu Island, off the coast of Kenya. Anderson announced their separation on April 21, 2006.\n\nAnderson and former boyfriend, Mark Griffiths, have two sons: Oscar, born November 2006 and Felix, born October 2008. She ended their relationship in 2012. In March 2012, Anderson told Out magazine about her past relationship with a girl while in high school.\n\nIn 1997, she was chosen by People magazine as one of the 50 Most Beautiful People in the World. Askmen listed her at No. 6 on their Top 7: \'90s Sex Symbols. In 2008, she was listed 21st in FHM\'s All Time 100 Sexiest Hall of Fame.'}}

            ],
            "air_day": "Monday",
            "air_time": "20:00",
            "certification": "TV-14",
            "country": "us",
            "first_aired": "Fri, 10 Sep 1993 07:00:00 GMT",
            "genres": [
                'drama',
                'mystery',
                'science fiction',
                'fantasy'
            ],
            "homepage": "http://www.fox.com/the-x-files",
            "id": 4063,
            "images": {
                "banner": {
                    "full": "https://walter.trakt.us/images/shows/000/004/063/banners/original/0927751ec8.jpg"
                },
                "clearart": {
                    "full": "https://walter.trakt.us/images/shows/000/004/063/cleararts/original/a4a0db2c8d.png"
                },
                "fanart": {
                    "full": "https://walter.trakt.us/images/shows/000/004/063/fanarts/original/1f0b461052.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/004/063/fanarts/medium/1f0b461052.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/004/063/fanarts/thumb/1f0b461052.jpg"
                },
                "logo": {
                    "full": "https://walter.trakt.us/images/shows/000/004/063/logos/original/ba7ac727c2.png"
                },
                "poster": {
                    "full": "https://walter.trakt.us/images/shows/000/004/063/posters/original/034cc070a9.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/004/063/posters/medium/034cc070a9.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/004/063/posters/thumb/034cc070a9.jpg"
                },
                "thumb": {
                    "full": "https://walter.trakt.us/images/shows/000/004/063/thumbs/original/74d4f3d798.jpg"
                }
            },
            "imdb_id": "tt0106179",
            "language": "en",
            "network": "FOX (US)",
            "overview": "The X-Files focused on the exploits of FBI Agents Fox Mulder, Dana Scully, John Doggett and Monica Reyes and their investigations into the paranormal. From genetic mutants and killer insects to a global conspiracy concerning the colonization of Earth by an alien species, this mind-boggling, humorous and occasionally frightening series created by Chris Carter has been one of the world's most popular sci-fi/drama shows since its humble beginnings in 1993.",
            "runtime": 45,
            "slug": "the-x-files",
            "timezone": "America/New_York",
            "title": "The X-Files",
            "tmdb_id": 4087,
            "tvdb_id": 77398,
            "tvrage_id": 6312,
            "year": 1993
        }

        rsp = api_client.get('/trakt/series/the x-files/?include_actors=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_translations_param(self, api_client):
        expected_payload = {
            "air_day": "Sunday",
            "air_time": "21:00",
            "certification": "TV-MA",
            "country": "us",
            "first_aired": "Sun, 17 Apr 2011 07:00:00 GMT",
            "genres": [
                "drama",
                "fantasy",
                "science fiction",
                "action",
                "adventure"
            ],
            "homepage": "http://www.hbo.com/game-of-thrones",
            "id": 1390,
            "images": {
                "banner": {
                    "full": "https://walter.trakt.us/images/shows/000/001/390/banners/original/9fefff703d.jpg"
                },
                "clearart": {
                    "full": "https://walter.trakt.us/images/shows/000/001/390/cleararts/original/5cbde9e647.png"
                },
                "fanart": {
                    "full": "https://walter.trakt.us/images/shows/000/001/390/fanarts/original/76d5df8aed.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/001/390/fanarts/medium/76d5df8aed.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/001/390/fanarts/thumb/76d5df8aed.jpg"
                },
                "logo": {
                    "full": "https://walter.trakt.us/images/shows/000/001/390/logos/original/13b614ad43.png"
                },
                "poster": {
                    "full": "https://walter.trakt.us/images/shows/000/001/390/posters/original/93df9cd612.jpg",
                    "medium": "https://walter.trakt.us/images/shows/000/001/390/posters/medium/93df9cd612.jpg",
                    "thumb": "https://walter.trakt.us/images/shows/000/001/390/posters/thumb/93df9cd612.jpg"
                },
                "thumb": {
                    "full": "https://walter.trakt.us/images/shows/000/001/390/thumbs/original/7beccbd5a1.jpg"
                }
            },
            "imdb_id": "tt0944947",
            "language": "en",
            "network": "HBO",
            "overview": "Seven noble families fight for control of the mythical land of Westeros. Friction between the houses leads to full-scale war. All while a very ancient evil awakens in the farthest north. Amidst the war, a neglected military order of misfits, the Night's Watch, is all that stands between the realms of men and the icy horrors beyond.",
            "runtime": 55,
            "slug": "game-of-thrones",
            "timezone": "America/New_York",
            "title": "Game of Thrones",
            "tmdb_id": 1399,
            "translations": {
                u'el': {
                    u'overview': u'\u0391\u03c0\u03cc \u03c4\u03b9\u03c2 \u03ba\u03cc\u03ba\u03ba\u03b9\u03bd\u03b5\u03c2 \u03b1\u03bc\u03bc\u03bf\u03c5\u03b4\u03b9\u03ad\u03c2 \u03c4\u03bf\u03c5 \u039d\u03cc\u03c4\u03bf\u03c5 \u03ba\u03b1\u03b9 \u03c4\u03b9\u03c2 \u03ac\u03b3\u03c1\u03b9\u03b5\u03c2 \u03c0\u03b5\u03b4\u03b9\u03ac\u03b4\u03b5\u03c2 \u03c4\u03b7\u03c2 \u0391\u03bd\u03b1\u03c4\u03bf\u03bb\u03ae\u03c2 \u03ad\u03c9\u03c2 \u03c4\u03bf\u03bd \u03c0\u03b1\u03b3\u03c9\u03bc\u03ad\u03bd\u03bf \u0392\u03bf\u03c1\u03c1\u03ac \u03ba\u03b1\u03b9 \u03c4\u03bf \u03b1\u03c1\u03c7\u03b1\u03af\u03bf \u03a4\u03b5\u03af\u03c7\u03bf\u03c2, \u03c0\u03bf\u03c5 \u03c0\u03c1\u03bf\u03c3\u03c4\u03b1\u03c4\u03b5\u03cd\u03b5\u03b9 \u03c4\u03bf \u03a3\u03c4\u03ad\u03bc\u03bc\u03b1 \u03b1\u03c0\u03cc \u03c3\u03ba\u03bf\u03c4\u03b5\u03b9\u03bd\u03ac \u03cc\u03bd\u03c4\u03b1, \u03bf\u03b9 \u03b9\u03c3\u03c7\u03c5\u03c1\u03ad\u03c2 \u03bf\u03b9\u03ba\u03bf\u03b3\u03ad\u03bd\u03b5\u03b9\u03b5\u03c2 \u03c4\u03c9\u03bd \u0395\u03c0\u03c4\u03ac \u0392\u03b1\u03c3\u03b9\u03bb\u03b5\u03af\u03c9\u03bd \u03b5\u03c0\u03b9\u03b4\u03af\u03b4\u03bf\u03bd\u03c4\u03b1\u03b9 \u03c3\u03b5 \u03bc\u03b9\u03b1 \u03b1\u03bd\u03b5\u03bb\u03ad\u03b7\u03c4\u03b7 \u03bc\u03ac\u03c7\u03b7 \u03c3\u03c4\u03b7 \u03b4\u03b9\u03b1\u03b4\u03bf\u03c7\u03ae \u03c4\u03bf\u03c5 \u03a3\u03b9\u03b4\u03b5\u03c1\u03ad\u03bd\u03b9\u03bf\u03c5 \u0398\u03c1\u03cc\u03bd\u03bf\u03c5. \u039c\u03b9\u03b1 \u03b9\u03c3\u03c4\u03bf\u03c1\u03af\u03b1 \u03b3\u03b5\u03bc\u03ac\u03c4\u03b7 \u03af\u03bd\u03c4\u03c1\u03b9\u03b3\u03ba\u03b5\u03c2 \u03ba\u03b1\u03b9 \u03c0\u03c1\u03bf\u03b4\u03bf\u03c3\u03af\u03b5\u03c2, \u03b9\u03c0\u03c0\u03bf\u03c4\u03b9\u03c3\u03bc\u03cc \u03ba\u03b1\u03b9 \u03c4\u03b9\u03bc\u03ae, \u03ba\u03b1\u03c4\u03b1\u03ba\u03c4\u03ae\u03c3\u03b5\u03b9\u03c2 \u03ba\u03b1\u03b9 \u03b8\u03c1\u03b9\u03ac\u03bc\u03b2\u03bf\u03c5\u03c2. \u03a3\u03c4\u03bf \u03a0\u03b1\u03b9\u03c7\u03bd\u03af\u03b4\u03b9 \u03c4\u03bf\u03c5 \u03a3\u03c4\u03ad\u03bc\u03bc\u03b1\u03c4\u03bf\u03c2, \u03b8\u03b1 \u03bd\u03b9\u03ba\u03ae\u03c3\u03b5\u03b9\u03c2 \u03ae \u03b8\u03b1 \u03c0\u03b5\u03b8\u03ac\u03bd\u03b5\u03b9\u03c2.',
                    u'title': u'Game of Thrones', u'tagline': None}, u'en': {
                    u'overview': u"Seven noble families fight for control of the mythical land of Westeros. Friction between the houses leads to full-scale war. All while a very ancient evil awakens in the farthest north. Amidst the war, a neglected military order of misfits, the Night's Watch, is all that stands between the realms of men and icy horrors beyond.",
                    u'title': u'Game of Thrones', u'tagline': None}, u'zh': {
                    u'overview': u'\u6545\u4e8b\u80cc\u666f\u662f\u4e00\u4e2a\u865a\u6784\u7684\u4e16\u754c\uff0c\u4e3b\u8981\u5206\u4e3a\u4e24\u7247\u5927\u9646\uff0c\u4f4d\u4e8e\u897f\u9762\u7684\u662f\u201c\u65e5\u843d\u56fd\u5ea6\u201d\u7ef4\u65af\u7279\u6d1b\uff08Westeros\uff09\uff0c\u9762\u79ef\u7ea6\u7b49\u4e8e\u5357\u7f8e\u6d32\u3002\u4f4d\u4e8e\u4e1c\u9762\u7684\u662f\u4e00\u5757\u9762\u79ef\u3001\u5f62\u72b6\u8fd1\u4f3c\u4e8e\u4e9a\u6b27\u5927\u9646\u7684\u9646\u5730\u3002\u6545\u4e8b\u7684\u4e3b\u7ebf\u4fbf\u53d1\u751f\u5728\u7ef4\u65af\u7279\u6d1b\u5927\u9646\u4e0a\u3002\u4ece\u56fd\u738b\u52b3\u52c3\xb7\u62dc\u62c9\u5e2d\u6069\u524d\u5f80\u6b64\u5730\u62dc\u8bbf\u4ed6\u7684\u597d\u53cb\u4e34\u51ac\u57ce\u4e3b\u3001\u5317\u5883\u5b88\u62a4\u827e\u5fb7\xb7\u53f2\u5854\u514b\u5f00\u59cb\uff0c\u6e10\u6e10\u5c55\u793a\u4e86\u8fd9\u7247\u56fd\u5ea6\u7684\u5168\u8c8c\u3002\u5355\u7eaf\u7684\u56fd\u738b\uff0c\u803f\u76f4\u7684\u9996\u76f8\uff0c\u5404\u6000\u5fc3\u601d\u7684\u5927\u81e3\uff0c\u62e5\u5175\u81ea\u91cd\u7684\u56db\u65b9\u8bf8\u4faf\uff0c\u5168\u56fd\u4ec5\u9760\u7740\u4e00\u6839\u7ec6\u5f26\u7ef4\u7cfb\u7740\u8868\u9762\u7684\u548c\u5e73\uff0c\u800c\u5f53\u5f26\u65ad\u4e4b\u65f6\uff0c\u56fd\u5bb6\u518d\u5ea6\u9677\u5165\u65e0\u5c3d\u7684\u6218\u4e71\u4e4b\u4e2d\u3002\u800c\u66f4\u8ba9\u4eba\u60ca\u609a\u7684\u3001\u90a3\u4e9b\u8fdc\u53e4\u7684\u4f20\u8bf4\u548c\u65e9\u5df2\u706d\u7edd\u7684\u751f\u7269\uff0c\u6b63\u91cd\u65b0\u56de\u5230\u8fd9\u7247\u571f\u5730\u3002',
                    u'title': u'\u6743\u529b\u7684\u6e38\u620f', u'tagline': None},
                u'vi': {u'overview': u'', u'title': u'Game of Thrones', u'tagline': None},
                u'is': {u'overview': u'', u'title': u'Kr\xfanuleikar', u'tagline': None}, u'it': {
                    u'overview': u'Il Trono di Spade (Game of Thrones) \xe8 una serie televisiva statunitense di genere fantasy creata da David Benioff e D.B. Weiss, che ha debuttato il 17 aprile 2011 sul canale via cavo HBO. \xc8 nata come trasposizione televisiva del ciclo di romanzi Cronache del ghiaccio e del fuoco (A Song of Ice and Fire) di George R. R. Martin.\n\nLa serie racconta le avventure di molti personaggi che vivono in un grande mondo immaginario costituito principalmente da due continenti. Il centro pi\xf9 grande e civilizzato del continente occidentale \xe8 la citt\xe0 capitale Approdo del Re, dove risiede il Trono di Spade. La lotta per la conquista del trono porta le pi\xf9 grandi famiglie del continente a scontrarsi o allearsi tra loro in un contorto gioco del potere. Ma oltre agli uomini, emergono anche altre forze oscure e magiche.',
                    u'title': u'Il Trono di Spade', u'tagline': None},
                u'ar': {u'overview': u'', u'title': u'Game of Thrones', u'tagline': None}, u'fi': {
                    u'overview': u'George R.R. Martinin kirjoihin perustuva, eeppinen sarja valtataistelusta, kunniasta ja petoksesta myyttisess\xe4 Westerosissa',
                    u'title': u'Game of Thrones', u'tagline': None}, u'cs': {
                    u'overview': u'Kontinent, kde l\xe9ta trvaj\xed des\xedtky rok\u016f a zimy se mohou prot\xe1hnout na cel\xfd lidsk\xfd \u017eivot, za\u010d\xednaj\xed su\u017eovat nepokoje. V\u0161ech Sedm kr\xe1lovstv\xed Z\xe1padozem\xed \u2013 pletich\xe1\u0159sk\xfd jih, divok\xe9 v\xfdchodn\xed krajiny i ledov\xfd sever ohrani\u010den\xfd starobylou Zd\xed, kter\xe1 chr\xe1n\xed kr\xe1lovstv\xed p\u0159ed pronik\xe1n\xedm temnoty \u2013 je zm\xedt\xe1no bojem dvou mocn\xfdch rod\u016f na \u017eivot a na smrt o nadvl\xe1du nad celou \u0159\xed\u0161\xed. Zem\xed ot\u0159\xe1s\xe1 zrada, cht\xed\u010d, intriky a nadp\u0159irozen\xe9 s\xedly. Krvav\xfd boj o \u017delezn\xfd tr\u016fn, post nejvy\u0161\u0161\xedho vl\xe1dce Sedmi kr\xe1lovstv\xed, bude m\xedt nep\u0159edv\xeddateln\xe9 a dalekos\xe1hl\xe9 d\u016fsledky\u2026',
                    u'title': u'Hra o tr\u016fny', u'tagline': None},
                u'id': {u'overview': u'', u'title': u'Game of Thrones', u'tagline': None}, u'es': {
                    u'overview': u'Juego de Tronos es una serie de televisi\xf3n de drama y fantas\xeda creada para la HBO por David Benioff y D. B. Weiss. Es una adaptaci\xf3n de la saga de novelas de fantas\xeda Canci\xf3n de Hielo y Fuego de George R. R. Martin. La primera de las novelas es la que da nombre a la serie.\n\nLa serie, ambientada en los continentes ficticios de Westeros y Essos al final de un verano de una decada de duraci\xf3n, entrelaza varias l\xedneas argumentales. La primera sigue a los miembros de varias casas nobles inmersos en una guerra civil por conseguir el Trono de Hierro de los Siete Reinos. La segunda trata sobre la creciente amenaza de un inminente invierno y sobre las temibles criaturas del norte. La tercera relata los esfuerzos por reclamar el trono de los \xfaltimos miembros exiliados de una dinast\xeda destronada. A pesar de sus personajes moralmente ambiguos, la serie profundiza en los problemas de la jerarqu\xeda social, religi\xf3n, lealtad, corrupci\xf3n, sexo, guerra civil, crimen y castigo.',
                    u'title': u'Juego de Tronos', u'tagline': None}, u'ru': {
                    u'overview': u'\u041a \u043a\u043e\u043d\u0446\u0443 \u043f\u043e\u0434\u0445\u043e\u0434\u0438\u0442 \u0432\u0440\u0435\u043c\u044f \u0431\u043b\u0430\u0433\u043e\u0434\u0435\u043d\u0441\u0442\u0432\u0438\u044f, \u0438 \u043b\u0435\u0442\u043e, \u0434\u043b\u0438\u0432\u0448\u0435\u0435\u0441\u044f \u043f\u043e\u0447\u0442\u0438 \u0434\u0435\u0441\u044f\u0442\u0438\u043b\u0435\u0442\u0438\u0435, \u0443\u0433\u0430\u0441\u0430\u0435\u0442. \u0412\u043e\u043a\u0440\u0443\u0433 \u0441\u0440\u0435\u0434\u043e\u0442\u043e\u0447\u0438\u044f \u0432\u043b\u0430\u0441\u0442\u0438 \u0421\u0435\u043c\u0438 \u043a\u043e\u0440\u043e\u043b\u0435\u0432\u0441\u0442\u0432, \u0416\u0435\u043b\u0435\u0437\u043d\u043e\u0433\u043e \u0442\u0440\u043e\u043d\u0430, \u0437\u0440\u0435\u0435\u0442 \u0437\u0430\u0433\u043e\u0432\u043e\u0440, \u0438 \u0432 \u044d\u0442\u043e \u043d\u0435\u043f\u0440\u043e\u0441\u0442\u043e\u0435 \u0432\u0440\u0435\u043c\u044f \u043a\u043e\u0440\u043e\u043b\u044c \u0440\u0435\u0448\u0430\u0435\u0442 \u0438\u0441\u043a\u0430\u0442\u044c \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0438 \u0443 \u0434\u0440\u0443\u0433\u0430 \u044e\u043d\u043e\u0441\u0442\u0438 \u042d\u0434\u0434\u0430\u0440\u0434\u0430 \u0421\u0442\u0430\u0440\u043a\u0430. \u0412 \u043c\u0438\u0440\u0435, \u0433\u0434\u0435 \u0432\u0441\u0435 \u2014 \u043e\u0442 \u043a\u043e\u0440\u043e\u043b\u044f \u0434\u043e \u043d\u0430\u0435\u043c\u043d\u0438\u043a\u0430 \u2014 \u0440\u0432\u0443\u0442\u0441\u044f \u043a \u0432\u043b\u0430\u0441\u0442\u0438, \u043f\u043b\u0435\u0442\u0443\u0442 \u0438\u043d\u0442\u0440\u0438\u0433\u0438 \u0438 \u0433\u043e\u0442\u043e\u0432\u044b \u0432\u043e\u043d\u0437\u0438\u0442\u044c \u043d\u043e\u0436 \u0432 \u0441\u043f\u0438\u043d\u0443, \u0435\u0441\u0442\u044c \u043c\u0435\u0441\u0442\u043e \u0438 \u0431\u043b\u0430\u0433\u043e\u0440\u043e\u0434\u0441\u0442\u0432\u0443, \u0441\u043e\u0441\u0442\u0440\u0430\u0434\u0430\u043d\u0438\u044e \u0438 \u043b\u044e\u0431\u0432\u0438. \u041c\u0435\u0436\u0434\u0443 \u0442\u0435\u043c, \u043d\u0438\u043a\u0442\u043e \u043d\u0435 \u0437\u0430\u043c\u0435\u0447\u0430\u0435\u0442 \u043f\u0440\u043e\u0431\u0443\u0436\u0434\u0435\u043d\u0438\u0435 \u0442\u044c\u043c\u044b \u0438\u0437 \u043b\u0435\u0433\u0435\u043d\u0434 \u0434\u0430\u043b\u0435\u043a\u043e \u043d\u0430 \u0421\u0435\u0432\u0435\u0440\u0435 \u2014 \u0438 \u043b\u0438\u0448\u044c \u0421\u0442\u0435\u043d\u0430 \u0437\u0430\u0449\u0438\u0449\u0430\u0435\u0442 \u0436\u0438\u0432\u044b\u0445 \u043a \u044e\u0433\u0443 \u043e\u0442 \u043d\u0435\u0435.',
                    u'title': u'\u0418\u0433\u0440\u0430 \u043f\u0440\u0435\u0441\u0442\u043e\u043b\u043e\u0432',
                    u'tagline': None}, u'lb': {u'overview': u'', u'title': u'Game of Thrones', u'tagline': None}, u'pt': {
                    u'overview': u'Adaptada por David Benioff e Dan Weiss, a primeira temporada, com dez epis\xf3dios encomendados, ter\xe1 como base o livro \u201cGame of Thrones\u201d. Game of Thrones se passa em Westeros, uma terra reminiscente da Europa Medieval, onde as esta\xe7\xf5es duram por anos ou at\xe9 mesmo d\xe9cadas. A hist\xf3ria gira em torno de uma batalha entre os Sete Reinos, onde duas fam\xedlias dominantes est\xe3o lutando pelo controle do Trono de Ferro, cuja posse assegura a sobreviv\xeancia durante o inverno de 40 anos que est\xe1 por vir. A s\xe9rie \xe9 encabe\xe7ada por Lena Headey, Sean Bean e Mark Addy. Bean interpreta Eddard \u201cNed\u201d Stark, Lorde de Winterfell, um homem conhecido pelo seu senso de honra e justi\xe7a que se torna o principal conselheiro do Rei Robert, vivido por Addy.',
                    u'title': u'A Guerra dos Tronos', u'tagline': None},
                u'tw': {u'overview': u'', u'title': u'\u51b0\u8207\u706b\u4e4b\u6b4c\uff1a\u6b0a\u529b\u904a\u6232',
                        u'tagline': None}, u'tr': {
                    u'overview': u"Krall\u0131k dedi\u011fin sava\u015fs\u0131z olur mu? En g\xfc\xe7l\xfc krall\u0131\u011f\u0131 kurup, huzuru sa\u011flam\u0131\u015f olsan bile bu g\xfcc\xfc elinde nas\u0131l koruyacaks\u0131n? Burada yanl\u0131\u015f yapana yer yok, affetmek yok. Kuzey Krall\u0131\u011f\u0131n\u0131n h\xfck\xfcmdar\u0131 Lord Ned Stark, uzun ve zorlu sava\u015flardan sonra anayurduna d\xf6n\xfcp krall\u0131\u011f\u0131n\u0131 b\xfct\xfcnl\xfck i\xe7erisinde tutmay\u0131 ba\u015farm\u0131\u015ft\u0131r. Kral Robert Baratheon ile y\u0131llarca omuz omuza \xe7arp\u0131\u015fan ve Baratheon'un kral olmas\u0131n\u0131 sa\u011flayan Ned Stark'\u0131n tek istedi\u011fi kuzey s\u0131n\u0131rlar\u0131n\u0131 koruyan krall\u0131\u011f\u0131nda ailesiyle ve halk\u0131yla ya\u015famakt\u0131r. \n\nFakat suyun \xf6te yan\u0131nda kendi topraklar\u0131ndan ve krall\u0131\u011f\u0131ndan kovuldu\u011funu iddia eden Viserys Targaryen , k\u0131z karde\u015fi Daenerys'i barbar kavimlerin ba\u015f\u0131 Han Drogo'ya vererek, g\xfc\xe7 birli\u011fi planlar\u0131 yapmaktad\u0131r. Taht\u0131n\u0131 b\xfcy\xfck bir i\u015ftahla geri isteyen ama kraliyet oyunlar\u0131ndan habersiz olan Viserys'in planlar\u0131 Kral Baratheon'a ula\u015f\u0131r. Sava\u015f alan\u0131nda b\xfcy\xfck cengaver olan ama \xfclke ve aile y\xf6netiminde ayn\u0131 ba\u015far\u0131y\u0131 tutturamayan Baratheon'un tamamen g\xfcvenebilece\u011fi ve her yanl\u0131\u015f hamlesini arkas\u0131ndan toplayacak yeni bir sa\u011f kola ihtiyac\u0131 vard\u0131r. Kuzeyin Lordu Ned Stark bu g\xf6rev i\xe7in se\xe7ilen tek aday isimdir. K\u0131\u015f yakla\u015f\u0131yor...\n\nHanedan entrikalar\u0131, kap\u0131l\u0131 kap\u0131lar ard\u0131nda d\xf6nen oyunlar, birilerinin kuyusunu kazmak i\xe7in d\xfc\u015fman\u0131n koynuna girmekten \xe7ekinmeyen kad\u0131nlar, karde\u015fler aras\u0131 \xe7eki\u015fmeler, d\u0131\u015flanmalar... Hepsi tek bir hedef i\xe7in: taht kavgas\u0131..",
                    u'title': u'Taht Oyunlar\u0131', u'tagline': None},
                u'lt': {u'overview': u'', u'title': u'Sost\u0173 karai', u'tagline': None}, u'th': {u'overview': u'',
                                                                                                     u'title': u'\u0e40\u0e01\u0e21\u0e25\u0e48\u0e32\u0e1a\u0e31\u0e25\u0e25\u0e31\u0e07\u0e01\u0e4c',
                                                                                                     u'tagline': None},
                u'ro': {u'overview': u'', u'title': u'Urzeala tronurilor', u'tagline': None}, u'pl': {
                    u'overview': u'Siedem rodzin szlacheckich walczy o panowanie nad ziemiami krainy Westeros. Polityczne i seksualne intrygi s\u0105 na porz\u0105dku dziennym. Pierwszorz\u0119dne role wiod\u0105 rodziny: Stark, Lannister i Baratheon. Robert Baratheon, kr\xf3l Westeros, prosi swojego starego przyjaciela, Eddarda Starka, aby s\u0142u\u017cy\u0142 jako jego g\u0142\xf3wny doradca. Eddard, podejrzewaj\u0105c, \u017ce jego poprzednik na tym stanowisku zosta\u0142 zamordowany, przyjmuje propozycj\u0119, aby dog\u0142\u0119bnie zbada\u0107 spraw\u0119. Okazuje si\u0119, \u017ce przej\u0119cie tronu planuje kilka rodzin. Lannisterowie, familia kr\xf3lowej, staje si\u0119 podejrzana o podst\u0119pne knucie spisku. Po drugiej stronie morza, pozbawieni w\u0142adzy ostatni przedstawiciele poprzednio rz\u0105dz\u0105cego rodu, Targaryen\xf3w, r\xf3wnie\u017c planuj\u0105 odzyska\u0107 kontrol\u0119 nad kr\xf3lestwem. Narastaj\u0105cy konflikt pomi\u0119dzy rodzinami, do kt\xf3rego w\u0142\u0105czaj\u0105 si\u0119 r\xf3wnie\u017c inne rody, prowadzi do wojny. W mi\u0119dzyczasie na dalekiej p\xf3\u0142nocy budzi si\u0119 starodawne z\u0142o. W chaosie pe\u0142nym walk i konflikt\xf3w tylko grupa wyrzutk\xf3w zwana Nocn\u0105 Stra\u017c\u0105 stoi pomi\u0119dzy kr\xf3lestwem ludzi, a horrorem kryj\u0105cym si\u0119 poza nim.',
                    u'title': u'Gra o Tron', u'tagline': None}, u'fr': {
                    u'overview': u"Il y a tr\xe8s longtemps, \xe0 une \xe9poque oubli\xe9e, une force a d\xe9truit l'\xe9quilibre des saisons. Dans un pays o\xf9 l'\xe9t\xe9 peut durer plusieurs ann\xe9es et l'hiver toute une vie, des forces sinistres et surnaturelles se pressent aux portes du Royaume des Sept Couronnes. La confr\xe9rie de la Garde de Nuit, prot\xe9geant le Royaume de toute cr\xe9ature pouvant provenir d'au-del\xe0 du Mur protecteur, n'a plus les ressources n\xe9cessaires pour assurer la s\xe9curit\xe9 de tous. Apr\xe8s un \xe9t\xe9 de dix ann\xe9es, un hiver rigoureux s'abat sur le Royaume avec la promesse d'un avenir des plus sombres. Pendant ce temps, complots et rivalit\xe9s se jouent sur le continent pour s'emparer du Tr\xf4ne de fer, le symbole du pouvoir absolu.",
                    u'title': u'Game of Thrones', u'tagline': None}, u'bg': {
                    u'overview': u'\u201e\u0418\u0433\u0440\u0430 \u043d\u0430 \u0442\u0440\u043e\u043d\u043e\u0432\u0435\u201c \u0435 \u0441\u0435\u0440\u0438\u0430\u043b \u043d\u0430 HBO, \u043a\u043e\u0439\u0442\u043e \u0441\u043b\u0435\u0434\u0432\u0430 \u0438\u0441\u0442\u043e\u0440\u0438\u044f\u0442\u0430 \u043d\u0430 \u0444\u0435\u043d\u0442\u044a\u0437\u0438 \u0435\u043f\u043e\u0441 \u043f\u043e\u0440\u0435\u0434\u0438\u0446\u0430\u0442\u0430 \u201e\u041f\u0435\u0441\u0435\u043d \u0437\u0430 \u043e\u0433\u044a\u043d \u0438 \u043b\u0435\u0434\u201c, \u0432\u0437\u0435\u043c\u0430\u0439\u043a\u0438 \u0438\u043c\u0435\u0442\u043e \u043d\u0430 \u043f\u044a\u0440\u0432\u0430\u0442\u0430 \u043a\u043d\u0438\u0433\u0430. \u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435\u0442\u043e \u043d\u0430 \u0441\u0435\u0440\u0438\u0430\u043b\u0430 \u0441\u0435 \u0440\u0430\u0437\u0432\u0438\u0432\u0430 \u0432 \u0421\u0435\u0434\u0435\u043c\u0442\u0435 \u043a\u0440\u0430\u043b\u0441\u0442\u0432\u0430 \u043d\u0430 \u0412\u0435\u0441\u0442\u0435\u0440\u043e\u0441, \u043a\u044a\u0434\u0435\u0442\u043e \u043b\u044f\u0442\u043e\u0442\u043e \u043f\u0440\u043e\u0434\u044a\u043b\u0436\u0430\u0432\u0430 \u0434\u0435\u0441\u0435\u0442\u0438\u043b\u0435\u0442\u0438\u044f, \u0430 \u0437\u0438\u043c\u0430\u0442\u0430 \u2013 \u0446\u044f\u043b\u0430 \u0432\u0435\u0447\u043d\u043e\u0441\u0442.',
                    u'title': u'\u0418\u0433\u0440\u0430 \u043d\u0430 \u0442\u0440\u043e\u043d\u043e\u0432\u0435',
                    u'tagline': None}, u'hr': {
                    u'overview': u'Game of Thrones (Igra Prijestolja) srednjovjekovna je fantazija bazirana na seriji romana Georgea R. R. Martina smje\u0161tena u izmi\u0161ljenom svijetu Sedam kraljevina i prati dinasti\u010dka previranja i borbu nekoliko Ku\u0107a za kontrolu nad \u017deljeznim prijestoljem. Osim me\u0111usobnih borbi plemi\u0107kih obitelji, stanovni\u0161tvu prijeti natprirodna invazija s ledenog sjevera, prognana zmajeva princeza koja \u017eeli povratiti obiteljsko naslije\u0111e te zima koja \u0107e trajati godinama.\n\nNakon sumnjive smrti namjesnika kralja Roberta Baratheona, on sa svojom kraljicom Cersei iz bogate i iskvarene obitelji Lannister kre\u0107e na putovanje na sjever svome prijatelju knezu Eddardu Starku od O\u0161trozimlja, od kojega zatra\u017ei za postane novi Kraljev Namjesnik. Eddard nevoljko pristaje i tu zapo\u010dinje epska pri\u010da o \u010dasti i izdaji, ljubavi i mr\u017enji, tajnama i osveti...',
                    u'title': u'Igra Prijestolja', u'tagline': None}, u'de': {
                    u'overview': u'Die Handlung ist in einer fiktiven Welt angesiedelt und spielt auf den Kontinenten Westeros (den Sieben K\xf6nigreichen sowie im Gebiet der \u201eMauer\u201c und jenseits davon im Norden) und Essos. In dieser Welt ist die L\xe4nge der Sommer und Winter unvorhersehbar und variabel; eine Jahreszeit kann Jahre oder sogar Jahrzehnte dauern. Der Handlungsort auf dem Kontinent Westeros in den Sieben K\xf6nigreichen \xe4hnelt dabei stark dem mittelalterlichen Europa. Die Geschichte spielt am Ende eines langen Sommers und wird in drei Handlungsstr\xe4ngen weitgehend parallel erz\xe4hlt. In den Sieben K\xf6nigreichen bauen sich zwischen den m\xe4chtigsten Adelsh\xe4usern des Reiches Spannungen auf, die schlie\xdflich zum offenen Thronkampf f\xfchren. Gleichzeitig droht der Wintereinbruch und es zeichnet sich eine Gefahr durch eine fremde Rasse im hohen Norden von Westeros ab. Der dritte Handlungsstrang spielt auf dem Kontinent Essos, wo Daenerys Targaryen, Mitglied der vor Jahren abgesetzten K\xf6nigsfamilie, bestrebt ist, wieder an die Macht zu gelangen. Die komplexe Handlung umfasst zahlreiche Figuren und thematisiert unter anderem Politik und Machtk\xe4mpfe, Gesellschaftsverh\xe4ltnisse und Religion.',
                    u'title': u'Game of Thrones', u'tagline': None}, u'da': {
                    u'overview': u'George R. R. Martins Game of Thrones er en lang fort\xe6lling gennem syv b\xf8ger. Handlingen foreg\xe5r i et fiktivt kongerige kaldet Westeros. Denne middelalderlige verden er fuld af k\xe6mper, profetier og fortryllede skove, og bag en mur af is, der adskiller Riget, truer sp\xf8gelser og andre farer. Men de overnaturlige elementer er ikke rigtig s\xe5 fremtr\xe6dende i serien. Den narrative ramme er den hensynsl\xf8se kamp om magten, hvilket involverer en r\xe6kke konger, riddere og herrem\xe6nd med navne som Baratheon, Stark og Lannister. Det er ingen opl\xf8ftende historie, hvor det gode n\xf8dvendigvis sejrer frem for det onde, eller hvor det egentlig er s\xe5 let at afg\xf8re, hvad der er godt og ondt. Men Martin form\xe5r at tryllebinde publikum - ogs\xe5 dem, der normalt ikke synes om magi og fantasiverdener.',
                    u'title': u'Game of Thrones', u'tagline': None}, u'fa': {
                    u'overview': u'\u0647\u0641\u062a \u062e\u0627\u0646\u062f\u0627\u0646 \u0627\u0634\u0631\u0627\u0641\u06cc \u0628\u0631\u0627\u06cc \u062d\u0627\u06a9\u0645\u06cc\u062a \u0628\u0631 \u0633\u0631\u0632\u0645\u06cc\u0646 \u0627\u0641\u0633\u0627\u0646\u0647 \u0627\u06cc \xab\u0648\u0633\u062a\u0631\u0648\u0633\xbb \u062f\u0631 \u062d\u0627\u0644 \u0633\u062a\u06cc\u0632 \u0628\u0627 \u06cc\u06a9\u062f\u06cc\u06af\u0631\u0646\u062f. \u062e\u0627\u0646\u062f\u0627\u0646 \xab\u0627\u0633\u062a\u0627\u0631\u06a9\xbb\u060c \xab\u0644\u0646\u06cc\u0633\u062a\u0631\xbb \u0648 \xab\u0628\u0627\u0631\u0627\u062b\u06cc\u0648\u0646\xbb \u0628\u0631\u062c\u0633\u062a\u0647 \u062a\u0631\u06cc\u0646 \u0622\u0646\u0647\u0627 \u0647\u0633\u062a\u0646\u062f. \u062f\u0627\u0633\u062a\u0627\u0646 \u0627\u0632 \u062c\u0627\u06cc\u06cc \u0634\u0631\u0648\u0639 \u0645\u06cc \u0634\u0648\u062f \u06a9\u0647 \xab\u0631\u0627\u0628\u0631\u062a \u0628\u0627\u0631\u0627\u062b\u06cc\u0648\u0646\xbb \u067e\u0627\u062f\u0634\u0627\u0647 \u0648\u0633\u062a\u0631\u0648\u0633\u060c \u0627\u0632 \u062f\u0648\u0633\u062a \u0642\u062f\u06cc\u0645\u06cc \u0627\u0634\u060c \xab\u0627\u062f\u0627\u0631\u062f\xbb \u0627\u0631\u0628\u0627\u0628 \u062e\u0627\u0646\u062f\u0627\u0646 \u0627\u0633\u062a\u0627\u0631\u06a9\u060c \u062a\u0642\u0627\u0636\u0627 \u0645\u06cc \u06a9\u0646\u062f \u06a9\u0647 \u0628\u0639\u0646\u0648\u0627\u0646 \u0645\u0634\u0627\u0648\u0631 \u067e\u0627\u062f\u0634\u0627\u0647\u060c \u0628\u0631\u062a\u0631\u06cc\u0646 \u0633\u0645\u062a \u062f\u0631\u0628\u0627\u0631\u060c \u0628\u0647 \u0627\u0648 \u062e\u062f\u0645\u062a \u06a9\u0646\u062f. \u0627\u06cc\u0646 \u062f\u0631 \u062d\u0627\u0644\u06cc \u0627\u0633\u062a \u06a9\u0647 \u0645\u0634\u0627\u0648\u0631 \u0642\u0628\u0644\u06cc \u0628\u0647 \u0637\u0631\u0632 \u0645\u0631\u0645\u0648\u0632\u06cc \u0628\u0647 \u0642\u062a\u0644 \u0631\u0633\u06cc\u062f\u0647 \u0627\u0633\u062a\u060c \u0628\u0627 \u0627\u06cc\u0646 \u062d\u0627\u0644 \u0627\u062f\u0627\u0631\u062f \u062a\u0642\u0627\u0636\u0627\u06cc \u067e\u0627\u062f\u0634\u0627\u0647 \u0631\u0627 \u0645\u06cc \u067e\u0630\u06cc\u0631\u062f \u0648 \u0628\u0647 \u0633\u0631\u0632\u0645\u06cc\u0646 \u0634\u0627\u0647\u06cc \u0631\u0627\u0647\u06cc \u0645\u06cc \u0634\u0648\u062f. \u062e\u0627\u0646\u0648\u0627\u062f\u0647 \u0645\u0644\u06a9\u0647\u060c \u06cc\u0639\u0646\u06cc \u0644\u0646\u06cc\u0633\u062a\u0631 \u0647\u0627 \u062f\u0631 \u062d\u0627\u0644 \u062a\u0648\u0637\u0626\u0647 \u0628\u0631\u0627\u06cc \u0628\u062f\u0633\u062a \u0622\u0648\u0631\u062f\u0646 \u0642\u062f\u0631\u062a \u0647\u0633\u062a\u0646\u062f. \u0627\u0632 \u0633\u0648\u06cc \u062f\u06cc\u06af\u0631\u060c \u0628\u0627\u0632\u0645\u0627\u0646\u062f\u0647 \u0647\u0627\u06cc \u062e\u0627\u0646\u062f\u0627\u0646 \u067e\u0627\u062f\u0634\u0627\u0647 \u0642\u0628\u0644\u06cc \u0648\u0633\u062a\u0631\u0648\u0633\u060c \xab\u062a\u0627\u0631\u06af\u0631\u06cc\u0646 \u0647\u0627\xbb \u0646\u06cc\u0632 \u0646\u0642\u0634\u0647 \u06cc \u067e\u0633 \u06af\u0631\u0641\u062a\u0646 \u062a\u0627\u062c \u0648 \u062a\u062e\u062a \u0631\u0627 \u062f\u0631 \u0633\u0631 \u0645\u06cc \u067e\u0631\u0648\u0631\u0627\u0646\u0646\u062f\u060c \u0648 \u062a\u0645\u0627\u0645 \u0627\u06cc\u0646 \u0645\u0627\u062c\u0631\u0627\u0647\u0627 \u0645\u0648\u062c\u0628 \u062f\u0631 \u06af\u0631\u0641\u062a\u0646 \u0646\u0628\u0631\u062f\u06cc \u0639\u0638\u06cc\u0645 \u0645\u06cc\u0627\u0646 \u0622\u0646\u200c\u0647\u0627 \u062e\u0648\u0627\u0647\u062f \u0634\u062f...',
                    u'title': u'\u0628\u0627\u0632\u06cc \u062a\u0627\u062c \u0648 \u062a\u062e\u062a', u'tagline': None},
                u'bs': {
                    u'overview': u'Game of Thrones (Igra Prijestolja) srednjovjekovna je fantazija bazirana na seriji romana Georgea R. R. Martina smje\u0161tena u izmi\u0161ljenom svijetu Sedam kraljevina i prati dinasti\u010dka previranja i borbu nekoliko Ku\u0107a za kontrolu nad \u017deljeznim prijestoljem. Osim me\u0111usobnih borbi plemi\u0107kih obitelji, stanovni\u0161tvu prijeti natprirodna invazija s ledenog sjevera, prognana zmajeva princeza koja \u017eeli povratiti obiteljsko naslije\u0111e te zima koja \u0107e trajati godinama.\n\nNakon sumnjive smrti namjesnika kralja Roberta Baratheona, on sa svojom kraljicom Cersei iz bogate i iskvarene obitelji Lannister kre\u0107e na putovanje na sjever svome prijatelju knezu Eddardu Starku od O\u0161trozimlja, od kojega zatra\u017ei za postane novi Kraljev Namjesnik. Eddard nevoljko pristaje i tu zapo\u010dinje epska pri\u010da o \u010dasti i izdaji, ljubavi i mr\u017enji, tajnama i osveti...',
                    u'title': u'Game of Thrones', u'tagline': None}, u'nl': {
                    u'overview': u'Een eeuwenoude machtsstrijd barst los in het land waar de zomers decennia duren en de winters een leven lang kunnen aanslepen. Twee machtige geslachten - de regerende Baratheons en de verbannen Targaryens - maken zich op om de IJzeren Troon te claimen en de Zeven Koninkrijken van Westeros onder hun controle te krijgen. Maar in een tijdperk waarin verraad, lust, intriges en bovennatuurlijke krachten hoogtij vieren, zal hun dodelijke kat-en-muisspelletje onvoorziene en verreikende gevolgen hebben. Achter een eeuwenoude, gigantische muur van ijs in het uiterste noorden van Westeros maakt een kille vijand zich immers op om het land onder de voet te lopen. Gebaseerd op de bestseller fantasyreeks "A Song of Ice and Fire" van George R.R. Martin.',
                    u'title': u'Game of Thrones', u'tagline': None}, u'hu': {
                    u'overview': u'Westeros f\xf6l\xf6tt valaha a s\xe1rk\xe1nykir\xe1lyok uralkodtak, \xe1m a Targaryen-dinaszti\xe1t 15 \xe9vvel ezel\u0151tt el\u0171zt\xe9k, \xe9s most Robert Baratheon uralkodik h\u0171 bar\xe1tai, Jon Arryn, majd Eddard Stark seg\xedts\xe9g\xe9vel. A konfliktus k\xf6z\xe9ppontj\xe1ban Deres urai, a Starkok \xe1llnak. Olyanok, mint a f\xf6ld, ahol sz\xfclettek: makacs, kem\xe9ny jellem\u0171 csal\xe1d. Szem\xfcnk el\u0151tt h\u0151s\xf6k, gazemberek \xe9s egy gonosz hatalom t\xf6rt\xe9nete elevenedik meg. \xc1m hamar r\xe1 kell \xe9bredn\xfcnk, hogy ebben a vil\xe1gban m\xe9gsem egyszer\u0171en j\xf3k \xe9s gonoszok ker\xfclnek szembe egym\xe1ssal, hanem mesterien \xe1br\xe1zolt jellemek bontakoznak ki el\u0151tt\xfcnk k\xfcl\xf6nb\xf6z\u0151 v\xe1gyakkal, c\xe9lokkal, f\xe9lelmekkel \xe9s sebekkel. George R.R. Martin nagy siker\u0171, A t\u0171z \xe9s j\xe9g dala c\xedm\u0171 reg\xe9nyciklus\xe1nak els\u0151 k\xf6tete sorozat form\xe1j\xe1ban, amelyben k\xe9t nagyhatalm\xfa csal\xe1d v\xedv hal\xe1los harcot a Westeros H\xe9t Kir\xe1lys\xe1g\xe1nak ir\xe1ny\xedt.',
                    u'title': u'Tr\xf3nok harca', u'tagline': None}, u'he': {
                    u'overview': u'\u05de\u05e9\u05d7\u05e7\u05d9 \u05d4\u05db\u05e1 \u05e9\u05dc \u05d0\u05d9\u05d9\u05e5\'-\u05d1\u05d9-\u05d0\u05d5 \u05d4\u05d9\u05d0 \u05e2\u05d9\u05d1\u05d5\u05d3 \u05dc\u05d8\u05dc\u05d5\u05d5\u05d9\u05d6\u05d9\u05d4 \u05e9\u05dc \u05e1\u05d3\u05e8\u05ea \u05d4\u05e1\u05e4\u05e8\u05d9\u05dd \u05e8\u05d1\u05d9-\u05d4\u05de\u05db\u05e8 \u05e9\u05dc \u05d2\'\u05d5\u05e8\u05d2\' \u05e8.\u05e8. \u05de\u05e8\u05d8\u05d9\u05df ("\u05e9\u05d9\u05e8 \u05e9\u05dc \u05d0\u05e9 \u05d5\u05e9\u05dc \u05e7\u05e8\u05d7") \u05d1\u05d4\u05dd \u05d4\u05e7\u05d9\u05e5 \u05e0\u05de\u05e9\u05da \u05e2\u05dc \u05e4\u05e0\u05d9 \u05e2\u05e9\u05d5\u05e8\u05d9\u05dd, \u05d4\u05d7\u05d5\u05e8\u05e3 \u05d9\u05db\u05d5\u05dc \u05dc\u05d4\u05d9\u05de\u05e9\u05da \u05d3\u05d5\u05e8 \u05d5\u05d4\u05de\u05d0\u05d1\u05e7 \u05e2\u05dc \u05db\u05e1 \u05d4\u05d1\u05e8\u05d6\u05dc \u05d4\u05d7\u05dc. \u05d4\u05d5\u05d0 \u05d9\u05e9\u05ea\u05e8\u05e2 \u05de\u05df \u05d4\u05d3\u05e8\u05d5\u05dd, \u05d1\u05d5 \u05d4\u05d7\u05d5\u05dd \u05de\u05d5\u05dc\u05d9\u05d3 \u05de\u05d6\u05d9\u05de\u05d5\u05ea, \u05ea\u05d0\u05d5\u05d5\u05ea \u05d5\u05e7\u05e0\u05d5\u05e0\u05d9\u05d5\u05ea; \u05d0\u05dc \u05d0\u05d3\u05de\u05d5\u05ea \u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05e0\u05e8\u05d7\u05d1\u05d5\u05ea \u05d5\u05d4\u05e4\u05e8\u05d0\u05d9\u05d5\u05ea; \u05db\u05dc \u05d4\u05d3\u05e8\u05da \u05d0\u05dc \u05d4\u05e6\u05e4\u05d5\u05df \u05d4\u05e7\u05e4\u05d5\u05d0, \u05e9\u05dd \u05d7\u05d5\u05de\u05ea \u05e7\u05e8\u05d7 \u05d0\u05d3\u05d9\u05e8\u05d4 \u05de\u05d2\u05e0\u05d4 \u05e2\u05dc \u05d4\u05de\u05de\u05dc\u05db\u05d4 \u05de\u05e4\u05e0\u05d9 \u05db\u05d5\u05d7\u05d5\u05ea \u05d4\u05d0\u05d5\u05e4\u05dc \u05d4\u05e9\u05d5\u05db\u05e0\u05d9\u05dd \u05de\u05e6\u05d3\u05d4 \u05d4\u05e9\u05e0\u05d9. \u05de\u05dc\u05db\u05d9\u05dd \u05d5\u05de\u05dc\u05db\u05d5\u05ea, \u05d0\u05d1\u05d9\u05e8\u05d9\u05dd \u05d5\u05e4\u05d5\u05e8\u05e2\u05d9 \u05d7\u05d5\u05e7, \u05e9\u05e7\u05e8\u05e0\u05d9\u05dd, \u05d0\u05d3\u05d5\u05e0\u05d9\u05dd \u05d5\u05d0\u05e0\u05e9\u05d9\u05dd \u05d9\u05e9\u05e8\u05d9\u05dd. \u05e2\u05d5\u05dc\u05dd \u05d1\u05d5 \u05de\u05ea\u05d1\u05e9\u05dc\u05d5\u05ea \u05e7\u05e0\u05d5\u05e0\u05d9\u05d5\u05ea \u05d1\u05e6\u05d5\u05e8\u05ea \u05e0\u05d9\u05e1\u05d9\u05d5\u05e0\u05d5\u05ea \u05e8\u05e6\u05d7 \u05d5\u05de\u05d2\u05e2\u05d9\u05dd \u05d0\u05e1\u05d5\u05e8\u05d9\u05dd.',
                    u'title': u'\u05de\u05e9\u05d7\u05e7\u05d9 \u05d4\u05db\u05e1', u'tagline': None}, u'ko': {
                    u'overview': u'\uc218\uc2ed \ub144\uac04 \uc774\uc5b4\uc9c4 \uc5ec\ub984, \ud558\uc9c0\ub9cc \uc774\uc81c \uc601\uc6d0\ud788 \ub05d\ub098\uc9c0 \uc54a\uc744 \uaca8\uc6b8\uc774 \ub2e4\uac00\uc628\ub2e4.\n\n\uadf8\ub9ac\uace0... \ucca0\uc655\uc88c\ub97c \ub458\ub7ec\uc2fc \ud608\ud22c\uac00 \uc2dc\uc791\ub41c\ub2e4.\n\n\uc220\uc218\uc640 \ud0d0\uc695, \uc74c\ubaa8\uac00 \ub09c\ubb34\ud558\ub294 \ub0a8\ubd80\uc5d0\uc11c \uc57c\ub9cc\uc774 \uc228 \uc26c\ub294 \ub3d9\ubd80\uc758 \uad11\ud65c\ud55c \ub300\uc9c0, \uc5b4\ub460\uc758 \uc874\uc7ac\ub4e4\ub85c\ubd80\ud130 \uc655\uad6d\uc744 \uc9c0\ud0a4\uae30 \uc704\ud574 250M \ub192\uc774\uc758 \uc7a5\ubcbd\uc744 \uc313\uc740 \ubd81\ubd80\uc5d0 \uc774\ub974\uae30\uae4c\uc9c0 \ud3bc\uccd0\uc9c0\ub294 \ub300\uc11c\uc0ac\uc2dc.\n\n\uc655\ub4e4\uacfc \uc655\ube44\ub4e4, \uae30\uc0ac\ub4e4\uacfc \ubc30\uc2e0\uc790\ub4e4, \ubaa8\ub7b5\uac00\ub4e4, \uc601\uc8fc\ub4e4\uacfc \uc815\uc9c1\ud55c \uc778\ubb3c\ub4e4\uc774 \uc655\uc88c\uc758 \uac8c\uc784\uc744 \ubc8c\uc778\ub2e4.',
                    u'title': u'\uc655\uc88c\uc758 \uac8c\uc784', u'tagline': None}, u'sv': {
                    u'overview': u'Serien utspelar sig p\xe5 den fiktiva kontinenten Westeros, oftast kallad "De sju konungarikena". Eddard "Ned" Stark bekymras av rykten fr\xe5n muren i norr d\xe5 han f\xe5r besked om att Jon Arryn, hans mentor och kungens hand, d\xf6tt och att kung Robert Baratheon \xe4r p\xe5 v\xe4g till Vinterhed. P\xe5 andra sidan havet smider exilprinsen Viseras Targaryen planer f\xf6r att \xe5terer\xf6vra De sju konungarikena.',
                    u'title': u'Game of Thrones', u'tagline': None},
                u'sk': {u'overview': u'', u'title': u'Hra o Tr\xf3ny', u'tagline': None}, u'uk': {
                    u'overview': u'\u0421\u0435\u0440\u0456\u0430\u043b "\u0413\u0440\u0430 \u041f\u0440\u0435\u0441\u0442\u043e\u043b\u0456\u0432" \u0437\u043d\u044f\u0442\u043e \u0437\u0430 \u0441\u044e\u0436\u0435\u0442\u043e\u043c \u0444\u0435\u043d\u0442\u0435\u0437\u0456-\u0431\u0435\u0441\u0442\u0441\u0435\u043b\u0435\u0440\u0456\u0432 "\u041f\u0456\u0441\u043d\u044f \u043b\u044c\u043e\u0434\u0443 \u0456 \u043f\u043e\u043b\u0443\u043c\'\u044f" \u0414\u0436\u043e\u0440\u0434\u0436\u0430 \u0420.\u0420. \u041c\u0430\u0440\u0442\u0456\u043d\u0430 (\u0432\u043e\u043b\u043e\u0434\u0430\u0440\u044f \u043f\u0440\u0435\u043c\u0456\u0439 \u0413\'\u044e\u0491\u043e \u0442\u0430 \u041d\u0435\u0431\'\u044e\u043b\u0430). \u0417 \u043c\u043e\u043c\u0435\u043d\u0442\u0443 \u0441\u0432\u043e\u0433\u043e \u0441\u0442\u0432\u043e\u0440\u0435\u043d\u043d\u044f "\u0413\u0440\u0430 \u041f\u0440\u0435\u0441\u0442\u043e\u043b\u0456\u0432" \u0441\u0442\u0430\u0432 \u043e\u0434\u043d\u0438\u043c \u0437 \u043d\u0430\u0439\u0434\u043e\u0440\u043e\u0436\u0447\u0438\u0445 \u0444\u0435\u043d\u0442\u0435\u0437\u0456-\u0441\u0435\u0440\u0456\u0430\u043b\u0456\u0432 \u0432 \u0456\u0441\u0442\u043e\u0440\u0456\u0457 \u0442\u0435\u043b\u0435\u0431\u0430\u0447\u0435\u043d\u043d\u044f. \u0426\u0435 \u043e\u0434\u043d\u0430 \u0437 \u043f\u0440\u0438\u0447\u0438\u043d, \u0437 \u044f\u043a\u043e\u0457 \u0442\u0435\u043b\u0435\u043a\u0440\u0438\u0442\u0438\u043a\u0438 \u0432\u0432\u0430\u0436\u0430\u044e\u0442\u044c \u0441\u0435\u0440\u0456\u0430\u043b \u0433\u043e\u043b\u043e\u0432\u043d\u0438\u043c \u043f\u0440\u0435\u0442\u0435\u043d\u0434\u0435\u043d\u0442\u043e\u043c \u043d\u0430 \u043b\u0430\u0432\u0440\u0438 "\u0412\u043e\u043b\u043e\u0434\u0430\u0440\u0430 \u043f\u0435\u0440\u0441\u0442\u0435\u043d\u0456\u0432" (\u044f\u043a \u043f\u0435\u0440\u0448\u043e\u0432\u0456\u0434\u043a\u0440\u0438\u0432\u0430\u0447\u0430 \u0436\u0430\u043d\u0440\u0443) \u043d\u0430 \u0442\u0435\u043b\u0435\u0431\u0430\u0447\u0435\u043d\u043d\u0456.\n\n\u041f\u043e\u0434\u0456\u0457 \u0441\u0435\u0440\u0456\u0430\u043b\u0443 \u0440\u043e\u0437\u0433\u043e\u0440\u0442\u0430\u044e\u0442\u044c\u0441\u044f \u0443 \u0444\u0435\u043d\u0442\u0435\u0437\u0456\u0439\u043d\u043e\u043c\u0443 \u0441\u0432\u0456\u0442\u0456, \u043c\u0435\u0448\u043a\u0430\u043d\u0446\u044f\u043c\u0438 \u044f\u043a\u043e\u0433\u043e - \u0430\u043c\u0431\u0456\u0446\u0456\u0439\u043d\u0456 \u0447\u043e\u043b\u043e\u0432\u0456\u043a\u0438 \u0442\u0430 \u0436\u0456\u043d\u043a\u0438, \u043a\u043e\u0442\u0440\u0438\u043c \u043f\u0440\u0438\u0442\u0430\u043c\u0430\u043d\u043d\u0456 \u044f\u043a \u0433\u0456\u0434\u043d\u0456\u0441\u0442\u044c, \u0442\u0430\u043a \u0456 \u0440\u043e\u0437\u043f\u0443\u0441\u0442\u0430. \u041d\u0430\u0439\u0446\u0456\u043d\u043d\u0456\u0448\u0430 \u0440\u0456\u0447 \u0443 \u0446\u044c\u043e\u043c\u0443 \u041a\u043e\u0440\u043e\u043b\u0456\u0432\u0441\u0442\u0432\u0456 \u2013 \u0417\u0430\u043b\u0456\u0437\u043d\u0438\u0439 \u0422\u0440\u043e\u043d. \u0422\u043e\u0439, \u0445\u0442\u043e \u043d\u0438\u043c \u0432\u043e\u043b\u043e\u0434\u0456\u0454, \u043e\u0442\u0440\u0438\u043c\u0443\u0454 \u043d\u0435\u0439\u043c\u043e\u0432\u0456\u0440\u043d\u0443 \u0432\u043b\u0430\u0434\u0443 \u0456 \u0432\u0438\u0437\u043d\u0430\u043d\u043d\u044f.\n\n\u0417\u0430 \u043f\u0430\u043d\u0443\u0432\u0430\u043d\u043d\u044f \u0443 \u041a\u043e\u0440\u043e\u043b\u0456\u0432\u0441\u0442\u0432\u0456 \u0431\u043e\u0440\u0435\u0442\u044c\u0441\u044f \u043e\u0434\u0440\u0430\u0437\u0443 \u0434\u0435\u043a\u0456\u043b\u044c\u043a\u0430 \u0432\u0456\u0434\u043e\u043c\u0438\u0445 \u0440\u043e\u0434\u0438\u043d. \u0421\u0435\u0440\u0435\u0434 \u043d\u0438\u0445: \u0431\u043b\u0430\u0433\u043e\u0440\u043e\u0434\u043d\u0456 \u0421\u0442\u0430\u0440\u043a\u0438, \u0437\u043c\u043e\u0432\u043d\u0438\u043a\u0438 \u041b\u0430\u043d\u043d\u0456\u0441\u0442\u0435\u0440\u0438, \u043f\u0440\u0438\u043d\u0446\u0435\u0441\u0430 \u0434\u0440\u0430\u043a\u043e\u043d\u0456\u0432 \u0414\u0435\u0439\u043d\u0435\u0440\u0456\u0441 \u0456 \u0457\u0457 \u0436\u043e\u0440\u0441\u0442\u043e\u043a\u0438\u0439 \u0431\u0440\u0430\u0442 \u0412\u0456\u0437\u0435\u0440\u0456\u0441.\n\n"\u0413\u0440\u0430 \u043f\u0440\u0435\u0441\u0442\u043e\u043b\u0456\u0432" \u2013 \u0446\u0435 \u0456\u0441\u0442\u043e\u0440\u0456\u044f \u043f\u0440\u043e \u0434\u0432\u043e\u0432\u043b\u0430\u0434\u0434\u044f \u0456 \u0437\u0440\u0430\u0434\u0443, \u0433\u0456\u0434\u043d\u0456\u0441\u0442\u044c \u0456 \u0431\u0435\u0437\u0447\u0435\u0441\u0442\u044f, \u0437\u0430\u0432\u043e\u044e\u0432\u0430\u043d\u043d\u044f \u0439 \u0442\u0440\u0456\u0443\u043c\u0444. \u0406 \u043a\u043e\u0436\u043d\u043e\u0433\u043e \u0443\u0447\u0430\u0441\u043d\u0438\u043a\u0430 \u0446\u0456\u0454\u0457 \u0433\u0440\u0438 \u043e\u0447\u0456\u043a\u0443\u0454 \u0430\u0431\u043e \u043f\u0435\u0440\u0435\u043c\u043e\u0433\u0430, \u0430\u0431\u043e \u0441\u043c\u0435\u0440\u0442\u044c.',
                    u'title': u'\u0413\u0440\u0430 \u041f\u0440\u0435\u0441\u0442\u043e\u043b\u0456\u0432', u'tagline': None}

            },
            "tvdb_id": 121361,
            "tvrage_id": 24493,
            "year": 2011
        }

        rsp = api_client.get('/trakt/series/game of thrones/?include_translations=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload


@pytest.mark.online
class TestTraktMovieLookupAPI(object):
    config = 'tasks: {}'

    def test_trakt_movies_lookup_no_params(self, api_client):
        # Bad API call
        rsp = api_client.get('/trakt/movies/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        expected_payload = {
            "genres": [
                "action",
                "adventure",
                "science fiction",
                "thriller"
            ],
            "homepage": "http://www.warnerbros.com/movies/home-entertainment/the-matrix/37313ac7-9229-474d-a423-44b7a6bc1a54.html",
            "id": 481,
            "images": {
                "banner": {
                    "full": "https://walter.trakt.us/images/movies/000/000/481/banners/original/cd678b64e4.jpg"
                },
                "clearart": {
                    "full": "https://walter.trakt.us/images/movies/000/000/481/cleararts/original/2326f6588d.png"
                },
                "fanart": {
                    "full": "https://walter.trakt.us/images/movies/000/000/481/fanarts/original/c556867276.jpg",
                    "medium": "https://walter.trakt.us/images/movies/000/000/481/fanarts/medium/c556867276.jpg",
                    "thumb": "https://walter.trakt.us/images/movies/000/000/481/fanarts/thumb/c556867276.jpg"
                },
                "logo": {
                    "full": "https://walter.trakt.us/images/movies/000/000/481/logos/original/f5e05ed291.png"
                },
                "poster": {
                    "full": "https://walter.trakt.us/images/movies/000/000/481/posters/original/373310d2ee.jpg",
                    "medium": "https://walter.trakt.us/images/movies/000/000/481/posters/medium/373310d2ee.jpg",
                    "thumb": "https://walter.trakt.us/images/movies/000/000/481/posters/thumb/373310d2ee.jpg"
                },
                "thumb": {
                    "full": "https://walter.trakt.us/images/movies/000/000/481/thumbs/original/0a391c9cc8.jpg"
                }
            },
            "imdb_id": "tt0133093",
            "language": "en",
            "overview": "Thomas A. Anderson is a man living two lives. By day he is an average computer programmer and by night a malevolent hacker known as Neo, who finds himself targeted by the police when he is contacted by Morpheus, a legendary computer hacker, who reveals the shocking truth about our reality.",
            "released": 'Tue, 30 Mar 1999 00:00:00 GMT',
            "runtime": 136,
            "slug": "the-matrix-1999",
            "tagline": "Welcome to the Real World.",
            "title": "The Matrix",
            "tmdb_id": 603,
            "trailer": "http://youtube.com/watch?v=m8e-FF8MsqU",
            "year": 1999
        }

        rsp = api_client.get('/trakt/movies/the matrix/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload
