# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
from past.builtins import cmp
from builtins import *  # pylint: disable=unused-import, redefined-builtin
import pytest

from flexget.utils import json


@pytest.mark.online
class TestTraktLookupAPI(object):
    config = 'tasks: {}'

    @staticmethod
    def _clean_attributes(data):
        """
        Removes non constant attributes from response since they can change and will trigger a fail
        :param data: Original response json
        :return: Response json without non constant attributes
        """
        data.pop('cached_at')
        data.pop('votes')
        data.pop('updated_at')
        data.pop('rating')
        data.pop('status')
        data.pop('number_of_aired_episodes')
        return data

    def test_trakt_series_lookup(self, api_client):
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

        data = self._clean_attributes(json.loads(rsp.get_data(as_text=True)))
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

        data = self._clean_attributes(json.loads(rsp.get_data(as_text=True)))
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

        data = self._clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_tmdb_id_param(self, api_client):
        expected_payload = {
            "air_day": "Tuesday",
            "air_time": "20:00",
            "certification": "TV-14",
            "country": "us",
            "first_aired": "Wed, 08 Oct 2014 00:00:00 GMT",
            "genres": [
                "drama",
                "fantasy",
                "science fiction"
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
            "runtime": 44,
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

        data = self._clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_imdb_id_param(self, api_client):
        expected_payload = {
            "air_day": "Tuesday",
            "air_time": "20:00",
            "certification": "TV-14",
            "country": "us",
            "first_aired": "Wed, 08 Oct 2014 00:00:00 GMT",
            "genres": [
                "drama",
                "fantasy",
                "science fiction"
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
            "runtime": 44,
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

        data = self._clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_tvdb_id_param(self, api_client):
        expected_payload = {
            "air_day": "Tuesday",
            "air_time": "20:00",
            "certification": "TV-14",
            "country": "us",
            "first_aired": "Wed, 08 Oct 2014 00:00:00 GMT",
            "genres": [
                "drama",
                "fantasy",
                "science fiction"
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
            "runtime": 44,
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

        data = self._clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload

    def test_trakt_series_lookup_with_tvrage_id_param(self, api_client):
        expected_payload = {
            "air_day": "Tuesday",
            "air_time": "20:00",
            "certification": "TV-14",
            "country": "us",
            "first_aired": "Wed, 08 Oct 2014 00:00:00 GMT",
            "genres": [
                "drama",
                "fantasy",
                "science fiction"
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
            "runtime": 44,
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

        data = self._clean_attributes(json.loads(rsp.get_data(as_text=True)))
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

        data = self._clean_attributes(json.loads(rsp.get_data(as_text=True)))
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

        data = self._clean_attributes(json.loads(rsp.get_data(as_text=True)))
        assert data == expected_payload
