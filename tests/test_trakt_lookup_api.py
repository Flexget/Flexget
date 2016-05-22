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
                "thriller"
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
            "overview": "Central City Police forensic scientist Barry Allen's crime lab is struck by lightning. Allen's electrified body is flung into and shatters a cabinet of chemicals, which are both electrified and forced to interact with each other and with his physiology when they come into physical contact with his body. He soon discovers that the accident has changed his body's metabolism and as a result he has gained the ability to move at superhuman speed. \nBarry Allen has become the Flash.",
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

        rsp = api_client.get('/trakt/series/the flash/?trakt_id=75481')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_actors_param(self, api_client):
        expected_payload = {
            "actors": [
                {
                    "412714": {
                        "biography": "From Wikipedia, the free encyclopedia.\n\nMitchell Craig \"Mitch\" Pileggi (born April 5, 1952) is an American actor. Pileggi is known for playing FBI assistant director Walter Skinner on the long-running popular series The X-Files. He also had a recurring role on Stargate Atlantis as Col. Steven Caldwell. He appeared in the 2008 film, Flash of Genius.",
                        "birthday": "1952/04/05",
                        "death": None,
                        "homepage": "",
                        "images": {
                            "fanart": {
                                "full": None,
                                "medium": None,
                                "thumb": None
                            },
                            "headshot": {
                                "full": "https://walter.trakt.us/images/person_shows/000/180/191/headshots/original/751e84197d.jpg",
                                "medium": "https://walter.trakt.us/images/person_shows/000/180/191/headshots/medium/751e84197d.jpg",
                                "thumb": "https://walter.trakt.us/images/person_shows/000/180/191/headshots/thumb/751e84197d.jpg"
                            }
                        },
                        "imdb_id": "nm0683379",
                        "name": "Mitch Pileggi",
                        "tmdb_id": "12644",
                        "trakt_id": 412714,
                        "trakt_slug": "mitch-pileggi"
                    },
                    "414777": {
                        "biography": "David William Duchovny (born August 7, 1960, height 6' 0½\" (1,84 m)) is an American actor, writer, and director. He is best known for playing Fox Mulder on The X-Files and Hank Moody on Californication, both of which have earned him Golden Globe awards  Duchovny was born in New York City, New York in 1960. He is the son of Margaret \"Meg\" (née Miller), a school administrator and teacher, and Amram \"Ami\" Ducovny (1927–2003), a writer and publicist who worked for the American Jewish Committee. His father was Jewish, from a family that immigrated from the Russian Empire and Poland. His mother is a Lutheran emigrant from Aberdeen, Scotland. His father dropped the h in his last name to avoid the sort of mispronunciations he encountered while serving in the Army.\n\nDuchovny attended Grace Church School and The Collegiate School For Boys; both are in Manhattan. He graduated from Princeton University in 1982 with a B.A. in English Literature. He was a member of Charter Club, one of the university's eating clubs. In 1982, his poetry received an honorable mention for a college prize from the Academy of American Poets. The title of his senior thesis was The Schizophrenic Critique of Pure Reason in Beckett's Early Novels. Duchovny played a season of junior varsity basketball as a shooting guard and centerfield for the varsity baseball team.\n\nHe received a Master of Arts in English Literature from Yale University and subsequently began work on a Ph.D. that remains unfinished. The title of his uncompleted doctoral thesis was Magic and Technology in Contemporary Poetry and Prose. At Yale, he was a student of popular literary critic Harold Bloom.\n\nDuchovny married actress Téa Leoni on May 6, 1997. In April 1999, Leoni gave birth to a daughter, Madelaine West Duchovny. Their second child, a son, Kyd Miller Duchovny, was born in June 2002. Duchovny is a former vegetarian and, as of 2007, is a pescetarian.\n\nOn August 28, 2008, Duchovny announced that he had checked himself into a rehabilitation facility for treating sex addiction. On October 15, 2008, Duchovny's and Leoni's representatives issued a statement revealing they had separated several months earlier.A week later, Duchovny's lawyer said that he planned to sue the Daily Mail over an article it ran that claimed he had an affair with Hungarian tennis instructor Edit Pakay while still married to Leoni, a claim that Duchovny has denied. On November 15, 2008, the Daily Mail retracted their claims. After getting back together, Duchovny and Leoni once again split on June 29, 2011.",
                        "birthday": "1960/08/07",
                        "death": None,
                        "homepage": "",
                        "images": {
                            "fanart": {
                                "full": "https://walter.trakt.us/images/people/000/414/777/fanarts/original/2ff7c2df63.jpg",
                                "medium": "https://walter.trakt.us/images/people/000/414/777/fanarts/medium/2ff7c2df63.jpg",
                                "thumb": "https://walter.trakt.us/images/people/000/414/777/fanarts/thumb/2ff7c2df63.jpg"
                            },
                            "headshot": {
                                "full": "https://walter.trakt.us/images/person_shows/000/160/968/headshots/original/7dbe745bf3.jpg",
                                "medium": "https://walter.trakt.us/images/person_shows/000/160/968/headshots/medium/7dbe745bf3.jpg",
                                "thumb": "https://walter.trakt.us/images/person_shows/000/160/968/headshots/thumb/7dbe745bf3.jpg"
                            }
                        },
                        "imdb_id": "nm0000141",
                        "name": "David Duchovny",
                        "tmdb_id": "12640",
                        "trakt_id": 414777,
                        "trakt_slug": "david-duchovny"
                    },
                    "9295": {
                        "biography": "From Wikipedia, the free encyclopedia.\n\nGillian Leigh Anderson (born August 9, 1968, height 5' 3\" (1,60 m)) is an American actress. After beginning her career in theatre, Anderson achieved international recognition for her role as Special Agent Dana Scully on the American television series The X-Files. Her film work includes The House of Mirth (2000), The Mighty Celt (2005), The Last King of Scotland (2006), and two X-Files films, The X-Files (1998) and The X-Files: I Want to Believe (2008).\n\nAnderson was born in Chicago, Illinois, the daughter of Rosemary Anderson (née Lane), a computer analyst, and Edward Anderson, who owned a film post-production company.Her father was of English descent, while her mother was of Irish and German ancestry. Soon after her birth, her family moved to Puerto Rico for 15 months; her family then moved to the United Kingdom where she lived until she was 11 years old. She lived for five years in Rosebery Gardens, Crouch End, London, and for 15 months in Albany Road, Stroud Green, London, so that her father could attend the London Film School.\n\nShe was a pupil of Coleridge Primary School. When Anderson was 11 years old, her family moved again, this time to Grand Rapids, Michigan. She attended Fountain Elementary and then City High-Middle School, a program for gifted students with a strong emphasis on the humanities; she graduated in 1986.\n\nAlong with other actors (notably Linda Thorson and John Barrowman) Anderson is bidialectal. With her English accent and background, Anderson was mocked and felt out of place in the American Midwest and soon adopted a Midwest accent. To this day, her accent depends on her location — for instance, in an interview with Jay Leno she spoke in an American accent, but shifted it for an interview with Michael Parkinson.\n\nAnderson was interested in marine biology, but began acting her freshman year in high school productions, and later in community theater, and served as a student intern at the Grand Rapids Civic Theatre &amp; School of Theatre Arts. She attended The Theatre School at DePaul University in Chicago (formerly the Goodman School of Drama), where she earned a Bachelor of Fine Arts in 1990. She also participated in the National Theatre of Great Britain's summer program at Cornell University.\n\nAnderson's brother died in 2011 of a brain tumor, at the age of 30.\n\nAnderson married her first husband, Clyde Klotz, The X-Files series assistant art director, on New Year's Day, 1994, in Hawaii in a Buddhist ceremony. They had a daughter, Piper Maru (born September 1994), for whom Chris Carter named the X-Files episode of the same name, and divorced in 1997.] In December 2004, Anderson married Julian Ozanne, a documentary filmmaker, on Lamu Island, off the coast of Kenya. Anderson announced their separation on April 21, 2006.\n\nAnderson and former boyfriend, Mark Griffiths, have two sons: Oscar, born November 2006 and Felix, born October 2008. She ended their relationship in 2012. In March 2012, Anderson told Out magazine about her past relationship with a girl while in high school.\n\nIn 1997, she was chosen by People magazine as one of the 50 Most Beautiful People in the World. Askmen listed her at No. 6 on their Top 7: '90s Sex Symbols. In 2008, she was listed 21st in FHM's All Time 100 Sexiest Hall of Fame.",
                        "birthday": "1968/08/09",
                        "death": None,
                        "homepage": "",
                        "images": {
                            "fanart": {
                                "full": "https://walter.trakt.us/images/people/000/009/295/fanarts/original/2ff7c2df63.jpg",
                                "medium": "https://walter.trakt.us/images/people/000/009/295/fanarts/medium/2ff7c2df63.jpg",
                                "thumb": "https://walter.trakt.us/images/people/000/009/295/fanarts/thumb/2ff7c2df63.jpg"
                            },
                            "headshot": {
                                "full": "https://walter.trakt.us/images/person_shows/000/160/967/headshots/original/508bae4b25.jpg",
                                "medium": "https://walter.trakt.us/images/person_shows/000/160/967/headshots/medium/508bae4b25.jpg",
                                "thumb": "https://walter.trakt.us/images/person_shows/000/160/967/headshots/thumb/508bae4b25.jpg"
                            }
                        },
                        "imdb_id": "nm0000096",
                        "name": "Gillian Anderson",
                        "tmdb_id": "12214",
                        "trakt_id": 9295,
                        "trakt_slug": "gillian-anderson"
                    }
                }
            ],
            "air_day": "Monday",
            "air_time": "20:00",
            "certification": "TV-14",
            "country": "us",
            "first_aired": "Fri, 10 Sep 1993 07:00:00 GMT",
            "genres": [
                "drama",
                "mystery",
                "science fiction",
                "thriller"
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
                "ar": {
                    "overview": "",
                    "tagline": None,
                    "title": "Game of Thrones"
                },
                "bg": {
                    "overview": "„Игра на тронове“ е сериал на HBO, който следва историята на фентъзи епос поредицата „Песен за огън и лед“, вземайки името на първата книга. Действието на сериала се развива в Седемте кралства на Вестерос, където лятото продължава десетилетия, а зимата – цяла вечност.",
                    "tagline": None,
                    "title": "Игра на тронове"
                },
                "bs": {
                    "overview": "Game of Thrones (Igra Prijestolja) srednjovjekovna je fantazija bazirana na seriji romana Georgea R. R. Martina smještena u izmišljenom svijetu Sedam kraljevina i prati dinastička previranja i borbu nekoliko Kuća za kontrolu nad Željeznim prijestoljem. Osim međusobnih borbi plemićkih obitelji, stanovništvu prijeti natprirodna invazija s ledenog sjevera, prognana zmajeva princeza koja želi povratiti obiteljsko naslijeđe te zima koja će trajati godinama.\n\nNakon sumnjive smrti namjesnika kralja Roberta Baratheona, on sa svojom kraljicom Cersei iz bogate i iskvarene obitelji Lannister kreće na putovanje na sjever svome prijatelju knezu Eddardu Starku od Oštrozimlja, od kojega zatraži za postane novi Kraljev Namjesnik. Eddard nevoljko pristaje i tu započinje epska priča o časti i izdaji, ljubavi i mržnji, tajnama i osveti...",
                    "tagline": None,
                    "title": "Game of Thrones"
                },
                "cs": {
                    "overview": "Kontinent, kde léta trvají desítky roků a zimy se mohou protáhnout na celý lidský život, začínají sužovat nepokoje. Všech Sedm království Západozemí – pletichářský jih, divoké východní krajiny i ledový sever ohraničený starobylou Zdí, která chrání království před pronikáním temnoty – je zmítáno bojem dvou mocných rodů na život a na smrt o nadvládu nad celou říší. Zemí otřásá zrada, chtíč, intriky a nadpřirozené síly. Krvavý boj o Železný trůn, post nejvyššího vládce Sedmi království, bude mít nepředvídatelné a dalekosáhlé důsledky…",
                    "tagline": None,
                    "title": "Hra o trůny"
                },
                "da": {
                    "overview": "George R. R. Martins Game of Thrones er en lang fortælling gennem syv bøger. Handlingen foregår i et fiktivt kongerige kaldet Westeros. Denne middelalderlige verden er fuld af kæmper, profetier og fortryllede skove, og bag en mur af is, der adskiller Riget, truer spøgelser og andre farer. Men de overnaturlige elementer er ikke rigtig så fremtrædende i serien. Den narrative ramme er den hensynsløse kamp om magten, hvilket involverer en række konger, riddere og herremænd med navne som Baratheon, Stark og Lannister. Det er ingen opløftende historie, hvor det gode nødvendigvis sejrer frem for det onde, eller hvor det egentlig er så let at afgøre, hvad der er godt og ondt. Men Martin formår at tryllebinde publikum - også dem, der normalt ikke synes om magi og fantasiverdener.",
                    "tagline": None,
                    "title": "Game of Thrones"
                },
                "de": {
                    "overview": "Die Handlung ist in einer fiktiven Welt angesiedelt und spielt auf den Kontinenten Westeros (den Sieben Königreichen sowie im Gebiet der „Mauer“ und jenseits davon im Norden) und Essos. In dieser Welt ist die Länge der Sommer und Winter unvorhersehbar und variabel; eine Jahreszeit kann Jahre oder sogar Jahrzehnte dauern. Der Handlungsort auf dem Kontinent Westeros in den Sieben Königreichen ähnelt dabei stark dem mittelalterlichen Europa. Die Geschichte spielt am Ende eines langen Sommers und wird in drei Handlungssträngen weitgehend parallel erzählt. In den Sieben Königreichen bauen sich zwischen den mächtigsten Adelshäusern des Reiches Spannungen auf, die schließlich zum offenen Thronkampf führen. Gleichzeitig droht der Wintereinbruch und es zeichnet sich eine Gefahr durch eine fremde Rasse im hohen Norden von Westeros ab. Der dritte Handlungsstrang spielt auf dem Kontinent Essos, wo Daenerys Targaryen, Mitglied der vor Jahren abgesetzten Königsfamilie, bestrebt ist, wieder an die Macht zu gelangen. Die komplexe Handlung umfasst zahlreiche Figuren und thematisiert unter anderem Politik und Machtkämpfe, Gesellschaftsverhältnisse und Religion.",
                    "tagline": None,
                    "title": "Game of Thrones"
                },
                "el": {
                    "overview": "Από τις κόκκινες αμμουδιές του Νότου και τις άγριες πεδιάδες της Ανατολής έως τον παγωμένο Βορρά και το αρχαίο Τείχος, που προστατεύει το Στέμμα από σκοτεινά όντα, οι ισχυρές οικογένειες των Επτά Βασιλείων επιδίδονται σε μια ανελέητη μάχη στη διαδοχή του Σιδερένιου Θρόνου. Μια ιστορία γεμάτη ίντριγκες και προδοσίες, ιπποτισμό και τιμή, κατακτήσεις και θριάμβους. Στο Παιχνίδι του Στέμματος, θα νικήσεις ή θα πεθάνεις.",
                    "tagline": None,
                    "title": "Game of Thrones"
                },
                "en": {
                    "overview": "Seven noble families fight for control of the mythical land of Westeros. Friction between the houses leads to full-scale war. All while a very ancient evil awakens in the farthest north. Amidst the war, a neglected military order of misfits, the Night's Watch, is all that stands between the realms of men and icy horrors beyond.",
                    "tagline": None,
                    "title": "Game of Thrones"
                },
                "es": {
                    "overview": "Juego de Tronos es una serie de televisión de drama y fantasía creada para la HBO por David Benioff y D. B. Weiss. Es una adaptación de la saga de novelas de fantasía Canción de Hielo y Fuego de George R. R. Martin. La primera de las novelas es la que da nombre a la serie.\n\nLa serie, ambientada en los continentes ficticios de Westeros y Essos al final de un verano de una decada de duración, entrelaza varias líneas argumentales. La primera sigue a los miembros de varias casas nobles inmersos en una guerra civil por conseguir el Trono de Hierro de los Siete Reinos. La segunda trata sobre la creciente amenaza de un inminente invierno y sobre las temibles criaturas del norte. La tercera relata los esfuerzos por reclamar el trono de los últimos miembros exiliados de una dinastía destronada. A pesar de sus personajes moralmente ambiguos, la serie profundiza en los problemas de la jerarquía social, religión, lealtad, corrupción, sexo, guerra civil, crimen y castigo.",
                    "tagline": None,
                    "title": "Juego de Tronos"
                },
                "fa": {
                    "overview": "هفت خاندان اشرافی برای حاکمیت بر سرزمین افسانه ای «وستروس» در حال ستیز با یکدیگرند. خاندان «استارک»، «لنیستر» و «باراثیون» برجسته ترین آنها هستند. داستان از جایی شروع می شود که «رابرت باراثیون» پادشاه وستروس، از دوست قدیمی اش، «ادارد» ارباب خاندان استارک، تقاضا می کند که بعنوان مشاور پادشاه، برترین سمت دربار، به او خدمت کند. این در حالی است که مشاور قبلی به طرز مرموزی به قتل رسیده است، با این حال ادارد تقاضای پادشاه را می پذیرد و به سرزمین شاهی راهی می شود. خانواده ملکه، یعنی لنیستر ها در حال توطئه برای بدست آوردن قدرت هستند. از سوی دیگر، بازمانده های خاندان پادشاه قبلی وستروس، «تارگرین ها» نیز نقشه ی پس گرفتن تاج و تخت را در سر می پرورانند، و تمام این ماجراها موجب در گرفتن نبردی عظیم میان آن‌ها خواهد شد...",
                    "tagline": None,
                    "title": "بازی تاج و تخت"
                },
                "fi": {
                    "overview": "George R.R. Martinin kirjoihin perustuva, eeppinen sarja valtataistelusta, kunniasta ja petoksesta myyttisessä Westerosissa",
                    "tagline": None,
                    "title": "Game of Thrones"
                },
                "fr": {
                    "overview": "Il y a très longtemps, à une époque oubliée, une force a détruit l'équilibre des saisons. Dans un pays où l'été peut durer plusieurs années et l'hiver toute une vie, des forces sinistres et surnaturelles se pressent aux portes du Royaume des Sept Couronnes. La confrérie de la Garde de Nuit, protégeant le Royaume de toute créature pouvant provenir d'au-delà du Mur protecteur, n'a plus les ressources nécessaires pour assurer la sécurité de tous. Après un été de dix années, un hiver rigoureux s'abat sur le Royaume avec la promesse d'un avenir des plus sombres. Pendant ce temps, complots et rivalités se jouent sur le continent pour s'emparer du Trône de fer, le symbole du pouvoir absolu.",
                    "tagline": None,
                    "title": "Le Trône de fer"
                },
                "he": {
                    "overview": "משחקי הכס של אייץ'-בי-או היא עיבוד לטלוויזיה של סדרת הספרים רבי-המכר של ג'ורג' ר.ר. מרטין (\"שיר של אש ושל קרח\") בהם הקיץ נמשך על פני עשורים, החורף יכול להימשך דור והמאבק על כס הברזל החל. הוא ישתרע מן הדרום, בו החום מוליד מזימות, תאוות וקנוניות; אל אדמות המזרח הנרחבות והפראיות; כל הדרך אל הצפון הקפוא, שם חומת קרח אדירה מגנה על הממלכה מפני כוחות האופל השוכנים מצדה השני. מלכים ומלכות, אבירים ופורעי חוק, שקרנים, אדונים ואנשים ישרים. עולם בו מתבשלות קנוניות בצורת ניסיונות רצח ומגעים אסורים.",
                    "tagline": None,
                    "title": "משחקי הכס"
                },
                "hr": {
                    "overview": "Game of Thrones (Igra Prijestolja) srednjovjekovna je fantazija bazirana na seriji romana Georgea R. R. Martina smještena u izmišljenom svijetu Sedam kraljevina i prati dinastička previranja i borbu nekoliko Kuća za kontrolu nad Željeznim prijestoljem. Osim međusobnih borbi plemićkih obitelji, stanovništvu prijeti natprirodna invazija s ledenog sjevera, prognana zmajeva princeza koja želi povratiti obiteljsko naslijeđe te zima koja će trajati godinama.\n\nNakon sumnjive smrti namjesnika kralja Roberta Baratheona, on sa svojom kraljicom Cersei iz bogate i iskvarene obitelji Lannister kreće na putovanje na sjever svome prijatelju knezu Eddardu Starku od Oštrozimlja, od kojega zatraži za postane novi Kraljev Namjesnik. Eddard nevoljko pristaje i tu započinje epska priča o časti i izdaji, ljubavi i mržnji, tajnama i osveti...",
                    "tagline": None,
                    "title": "Igra Prijestolja"
                },
                "hu": {
                    "overview": "Westeros fölött valaha a sárkánykirályok uralkodtak, ám a Targaryen-dinasztiát 15 évvel ezelőtt elűzték, és most Robert Baratheon uralkodik hű barátai, Jon Arryn, majd Eddard Stark segítségével. A konfliktus középpontjában Deres urai, a Starkok állnak. Olyanok, mint a föld, ahol születtek: makacs, kemény jellemű család. Szemünk előtt hősök, gazemberek és egy gonosz hatalom története elevenedik meg. Ám hamar rá kell ébrednünk, hogy ebben a világban mégsem egyszerűen jók és gonoszok kerülnek szembe egymással, hanem mesterien ábrázolt jellemek bontakoznak ki előttünk különböző vágyakkal, célokkal, félelmekkel és sebekkel. George R.R. Martin nagy sikerű, A tűz és jég dala című regényciklusának első kötete sorozat formájában, amelyben két nagyhatalmú család vív halálos harcot a Westeros Hét Királyságának irányít.",
                    "tagline": None,
                    "title": "Trónok harca"
                },
                "id": {
                    "overview": "",
                    "tagline": None,
                    "title": "Game of Thrones"
                },
                "is": {
                    "overview": "",
                    "tagline": None,
                    "title": "Krúnuleikar"
                },
                "it": {
                    "overview": "Il Trono di Spade (Game of Thrones) è una serie televisiva statunitense di genere fantasy creata da David Benioff e D.B. Weiss, che ha debuttato il 17 aprile 2011 sul canale via cavo HBO. È nata come trasposizione televisiva del ciclo di romanzi Cronache del ghiaccio e del fuoco (A Song of Ice and Fire) di George R. R. Martin.\n\nLa serie racconta le avventure di molti personaggi che vivono in un grande mondo immaginario costituito principalmente da due continenti. Il centro più grande e civilizzato del continente occidentale è la città capitale Approdo del Re, dove risiede il Trono di Spade. La lotta per la conquista del trono porta le più grandi famiglie del continente a scontrarsi o allearsi tra loro in un contorto gioco del potere. Ma oltre agli uomini, emergono anche altre forze oscure e magiche.",
                    "tagline": None,
                    "title": "Il Trono di Spade"
                },
                "ko": {
                    "overview": "수십 년간 이어진 여름, 하지만 이제 영원히 끝나지 않을 겨울이 다가온다.\n\n그리고... 철왕좌를 둘러싼 혈투가 시작된다.\n\n술수와 탐욕, 음모가 난무하는 남부에서 야만이 숨 쉬는 동부의 광활한 대지, 어둠의 존재들로부터 왕국을 지키기 위해 250M 높이의 장벽을 쌓은 북부에 이르기까지 펼쳐지는 대서사시.\n\n왕들과 왕비들, 기사들과 배신자들, 모략가들, 영주들과 정직한 인물들이 왕좌의 게임을 벌인다.",
                    "tagline": None,
                    "title": "왕좌의 게임"
                },
                "lb": {
                    "overview": "",
                    "tagline": None,
                    "title": "Game of Thrones"
                },
                "lt": {
                    "overview": "",
                    "tagline": None,
                    "title": "Sostų karai"
                },
                "nl": {
                    "overview": "Een eeuwenoude machtsstrijd barst los in het land waar de zomers decennia duren en de winters een leven lang kunnen aanslepen. Twee machtige geslachten - de regerende Baratheons en de verbannen Targaryens - maken zich op om de IJzeren Troon te claimen en de Zeven Koninkrijken van Westeros onder hun controle te krijgen. Maar in een tijdperk waarin verraad, lust, intriges en bovennatuurlijke krachten hoogtij vieren, zal hun dodelijke kat-en-muisspelletje onvoorziene en verreikende gevolgen hebben. Achter een eeuwenoude, gigantische muur van ijs in het uiterste noorden van Westeros maakt een kille vijand zich immers op om het land onder de voet te lopen. Gebaseerd op de bestseller fantasyreeks \"A Song of Ice and Fire\" van George R.R. Martin.",
                    "tagline": None,
                    "title": "Game of Thrones"
                },
                "pl": {
                    "overview": "Siedem rodzin szlacheckich walczy o panowanie nad ziemiami krainy Westeros. Polityczne i seksualne intrygi są na porządku dziennym. Pierwszorzędne role wiodą rodziny: Stark, Lannister i Baratheon. Robert Baratheon, król Westeros, prosi swojego starego przyjaciela, Eddarda Starka, aby służył jako jego główny doradca. Eddard, podejrzewając, że jego poprzednik na tym stanowisku został zamordowany, przyjmuje propozycję, aby dogłębnie zbadać sprawę. Okazuje się, że przejęcie tronu planuje kilka rodzin. Lannisterowie, familia królowej, staje się podejrzana o podstępne knucie spisku. Po drugiej stronie morza, pozbawieni władzy ostatni przedstawiciele poprzednio rządzącego rodu, Targaryenów, również planują odzyskać kontrolę nad królestwem. Narastający konflikt pomiędzy rodzinami, do którego włączają się również inne rody, prowadzi do wojny. W międzyczasie na dalekiej północy budzi się starodawne zło. W chaosie pełnym walk i konfliktów tylko grupa wyrzutków zwana Nocną Strażą stoi pomiędzy królestwem ludzi, a horrorem kryjącym się poza nim.",
                    "tagline": None,
                    "title": "Gra o Tron"
                },
                "pt": {
                    "overview": "Adaptada por David Benioff e Dan Weiss, a primeira temporada, com dez episódios encomendados, terá como base o livro “Game of Thrones”. Game of Thrones se passa em Westeros, uma terra reminiscente da Europa Medieval, onde as estações duram por anos ou até mesmo décadas. A história gira em torno de uma batalha entre os Sete Reinos, onde duas famílias dominantes estão lutando pelo controle do Trono de Ferro, cuja posse assegura a sobrevivência durante o inverno de 40 anos que está por vir. A série é encabeçada por Lena Headey, Sean Bean e Mark Addy. Bean interpreta Eddard “Ned” Stark, Lorde de Winterfell, um homem conhecido pelo seu senso de honra e justiça que se torna o principal conselheiro do Rei Robert, vivido por Addy.",
                    "tagline": None,
                    "title": "A Guerra dos Tronos"
                },
                "ro": {
                    "overview": "",
                    "tagline": None,
                    "title": "Urzeala tronurilor"
                },
                "ru": {
                    "overview": "К концу подходит время благоденствия, и лето, длившееся почти десятилетие, угасает. Вокруг средоточия власти Семи королевств, Железного трона, зреет заговор, и в это непростое время король решает искать поддержки у друга юности Эддарда Старка. В мире, где все — от короля до наемника — рвутся к власти, плетут интриги и готовы вонзить нож в спину, есть место и благородству, состраданию и любви. Между тем, никто не замечает пробуждение тьмы из легенд далеко на Севере — и лишь Стена защищает живых к югу от нее.",
                    "tagline": None,
                    "title": "Игра престолов"
                },
                "sk": {
                    "overview": "",
                    "tagline": None,
                    "title": "Hra o Tróny"
                },
                "sv": {
                    "overview": "Serien utspelar sig på den fiktiva kontinenten Westeros, oftast kallad \"De sju konungarikena\". Eddard \"Ned\" Stark bekymras av rykten från muren i norr då han får besked om att Jon Arryn, hans mentor och kungens hand, dött och att kung Robert Baratheon är på väg till Vinterhed. På andra sidan havet smider exilprinsen Viseras Targaryen planer för att återerövra De sju konungarikena.",
                    "tagline": None,
                    "title": "Game of Thrones"
                },
                "th": {
                    "overview": "",
                    "tagline": None,
                    "title": "เกมล่าบัลลังก์"
                },
                "tr": {
                    "overview": "Krallık dediğin savaşsız olur mu? En güçlü krallığı kurup, huzuru sağlamış olsan bile bu gücü elinde nasıl koruyacaksın? Burada yanlış yapana yer yok, affetmek yok. Kuzey Krallığının hükümdarı Lord Ned Stark, uzun ve zorlu savaşlardan sonra anayurduna dönüp krallığını bütünlük içerisinde tutmayı başarmıştır. Kral Robert Baratheon ile yıllarca omuz omuza çarpışan ve Baratheon'un kral olmasını sağlayan Ned Stark'ın tek istediği kuzey sınırlarını koruyan krallığında ailesiyle ve halkıyla yaşamaktır. \n\nFakat suyun öte yanında kendi topraklarından ve krallığından kovulduğunu iddia eden Viserys Targaryen , kız kardeşi Daenerys'i barbar kavimlerin başı Han Drogo'ya vererek, güç birliği planları yapmaktadır. Tahtını büyük bir iştahla geri isteyen ama kraliyet oyunlarından habersiz olan Viserys'in planları Kral Baratheon'a ulaşır. Savaş alanında büyük cengaver olan ama ülke ve aile yönetiminde aynı başarıyı tutturamayan Baratheon'un tamamen güvenebileceği ve her yanlış hamlesini arkasından toplayacak yeni bir sağ kola ihtiyacı vardır. Kuzeyin Lordu Ned Stark bu görev için seçilen tek aday isimdir. Kış yaklaşıyor...\n\nHanedan entrikaları, kapılı kapılar ardında dönen oyunlar, birilerinin kuyusunu kazmak için düşmanın koynuna girmekten çekinmeyen kadınlar, kardeşler arası çekişmeler, dışlanmalar... Hepsi tek bir hedef için: taht kavgası..",
                    "tagline": None,
                    "title": "Taht Oyunları"
                },
                "tw": {
                    "overview": "",
                    "tagline": None,
                    "title": "冰與火之歌：權力遊戲"
                },
                "uk": {
                    "overview": "Серіал \"Гра Престолів\" знято за сюжетом фентезі-бестселерів \"Пісня льоду і полум'я\" Джорджа Р.Р. Мартіна (володаря премій Г'юґо та Неб'юла). З моменту свого створення \"Гра Престолів\" став одним з найдорожчих фентезі-серіалів в історії телебачення. Це одна з причин, з якої телекритики вважають серіал головним претендентом на лаври \"Володара перстенів\" (як першовідкривача жанру) на телебаченні.\n\nПодії серіалу розгортаються у фентезійному світі, мешканцями якого - амбіційні чоловіки та жінки, котрим притаманні як гідність, так і розпуста. Найцінніша річ у цьому Королівстві – Залізний Трон. Той, хто ним володіє, отримує неймовірну владу і визнання.\n\nЗа панування у Королівстві бореться одразу декілька відомих родин. Серед них: благородні Старки, змовники Ланністери, принцеса драконів Дейнеріс і її жорстокий брат Візеріс.\n\n\"Гра престолів\" – це історія про двовладдя і зраду, гідність і безчестя, завоювання й тріумф. І кожного учасника цієї гри очікує або перемога, або смерть.",
                    "tagline": None,
                    "title": "Гра Престолів"
                },
                "vi": {
                    "overview": "",
                    "tagline": None,
                    "title": "Game of Thrones"
                },
                "zh": {
                    "overview": "故事背景是一个虚构的世界，主要分为两片大陆，位于西面的是“日落国度”维斯特洛（Westeros），面积约等于南美洲。位于东面的是一块面积、形状近似于亚欧大陆的陆地。故事的主线便发生在维斯特洛大陆上。从国王劳勃·拜拉席恩前往此地拜访他的好友临冬城主、北境守护艾德·史塔克开始，渐渐展示了这片国度的全貌。单纯的国王，耿直的首相，各怀心思的大臣，拥兵自重的四方诸侯，全国仅靠着一根细弦维系着表面的和平，而当弦断之时，国家再度陷入无尽的战乱之中。而更让人惊悚的、那些远古的传说和早已灭绝的生物，正重新回到这片土地。",
                    "tagline": None,
                    "title": "权力的游戏"
                }
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
            "released": None,
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
