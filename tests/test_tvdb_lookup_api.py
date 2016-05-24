# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import

from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.utils import json


@pytest.mark.online
class TestTVDBSeriesLookupAPI(object):
    config = 'tasks: {}'

    def test_tvdb_series_lookup(self, api_client):
        expected_response = {
            "airs_dayofweek": "Monday",
            "airs_time": "8:00 PM",
            "aliases": [
                "The X Files",
                "The X-Files (2016)",
                "The XFiles"
            ],
            "banner": "http://thetvdb.com/banners/graphical/61-g.jpg",
            "content_rating": "TV-14",
            "expired": False,
            "first_aired": "Fri, 10 Sep 1993 00:00:00 GMT",
            "genres": [
                "Mystery",
                "Science-Fiction"
            ],
            "imdb_id": "tt0106179",
            "language": "en",
            "last_updated": "2016-05-23 21:07:19",
            "network": "FOX (US)",
            "overview": "The X-Files focused on the exploits of FBI Agents Fox Mulder, Dana Scully, John Doggett and "
                        "Monica Reyes and their investigations into the paranormal. From genetic mutants and killer "
                        "insects to a global conspiracy concerning the colonization of Earth by an alien species, this"
                        " mind-boggling, humorous and occasionally frightening series created by Chris Carter has been"
                        " one of the world's most popular sci-fi/drama shows since its humble beginnings in 1993.",
            "posters": [
                "http://thetvdb.com/banners/posters/77398-1.jpg",
                "http://thetvdb.com/banners/posters/77398-2.jpg",
                "http://thetvdb.com/banners/posters/77398-3.jpg",
                "http://thetvdb.com/banners/posters/77398-4.jpg",
                "http://thetvdb.com/banners/posters/77398-6.jpg"
            ],
            "rating": 9,
            "runtime": 45,
            "series_name": "The X-Files",
            "status": "Continuing",
            "tvdb_id": 77398,
            "zap2it_id": "EP00080955"
        }

        rsp = api_client.get('/tvdb/series/The X-Files/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        assert data == expected_response


@pytest.mark.online
class TestTVDBSeriesWithActorsLookupAPI(object):
    config = 'tasks: {}'

    def test_tvdb_series_lookup_with_actors(self, api_client):
        expected_response = {
            "airs_dayofweek": "Monday",
            "airs_time": "8:00 PM",
            "aliases": [
                "The X Files",
                "The X-Files (2016)",
                "The XFiles"
            ],
            "actors": [
                "Annabeth Gish",
                "Mitch Pileggi",
                "Gillian Anderson",
                "David Duchovny",
                "Robert Patrick",
                "Dean Haglund",
                "Bruce Harwood",
                "Tom Braidwood",
                "William B. Davis",
                "Nicholas Lea",
                "James Pickens Jr.",
                "Cary Elwes",
                "Steven Williams",
                "Jerry Hardin",
                "Laurie Holden"
            ],
            "banner": "http://thetvdb.com/banners/graphical/61-g.jpg",
            "content_rating": "TV-14",
            "expired": False,
            "first_aired": "Fri, 10 Sep 1993 00:00:00 GMT",
            "genres": [
                "Mystery",
                "Science-Fiction"
            ],
            "imdb_id": "tt0106179",
            "language": "en",
            "last_updated": "2016-05-24 00:07:19",
            "network": "FOX (US)",
            "overview": "The X-Files focused on the exploits of FBI Agents Fox Mulder, Dana Scully, John Doggett and "
                        "Monica Reyes and their investigations into the paranormal. From genetic mutants and killer "
                        "insects to a global conspiracy concerning the colonization of Earth by an alien species, this"
                        " mind-boggling, humorous and occasionally frightening series created by Chris Carter has been"
                        " one of the world's most popular sci-fi/drama shows since its humble beginnings in 1993.",
            "posters": [
                "http://thetvdb.com/banners/posters/77398-1.jpg",
                "http://thetvdb.com/banners/posters/77398-2.jpg",
                "http://thetvdb.com/banners/posters/77398-3.jpg",
                "http://thetvdb.com/banners/posters/77398-4.jpg",
                "http://thetvdb.com/banners/posters/77398-6.jpg"
            ],
            "rating": 9,
            "runtime": 45,
            "series_name": "The X-Files",
            "status": "Continuing",
            "tvdb_id": 77398,
            "zap2it_id": "EP00080955"
        }

        rsp = api_client.get('/tvdb/series/The X-Files/?include_actors=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        assert data == expected_response


@pytest.mark.online
class TestTVDBEpisodeLookupAPI(object):
    config = 'tasks: {}'

    def test_tvdb_episode_lookup(self, api_client):
        rsp = api_client.get('/tvdb/episode/77398/')
        assert rsp.status_code == 500, 'Response code is %s' % rsp.status_code

        expected_response = {
            "absolute_number": None,
            "director": "Chris Carter",
            "episode_name": "My Struggle II",
            "episode_number": 6,
            "expired": False,
            "first_aired": "Mon, 22 Feb 2016 00:00:00 GMT",
            "id": 5313345,
            "image": "http://thetvdb.com/banners/episodes/77398/5313345.jpg",
            "last_update": 1456573658,
            "overview": "The investigations that Mulder and Scully began with Tad O’Malley have awakened powerful "
                        "enemies. A panic begins as people all over the country suddenly start falling ill, "
                        "and Scully looks for a cure. Mulder confronts the man whom he believes to be behind it all,"
                        " but another figure from their past may prove to be the key.",
            "rating": 7.3,
            "season_number": 10,
            "series_id": 77398
        }

        rsp = api_client.get('/tvdb/episode/77398/?season_number=10&ep_number=6')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        assert data == expected_response

        expected_response = {
            "absolute_number": 46,
            "director": "Antonio Negret",
            "episode_name": "The Race of His Life",
            "episode_number": 23,
            "expired": False,
            "first_aired": "Tue, 24 May 2016 00:00:00 GMT",
            "id": 5598674,
            "image": "http://thetvdb.com/banners/episodes/279121/5598674.jpg",
            "last_update": 1463604393,
            "overview": "Barry vows to stop Zoom after learning Zoom's true plans.",
            "rating": 0,
            "season_number": 2,
            "series_id": 279121
        }

        rsp = api_client.get('/tvdb/episode/279121/?absolute_number=46')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        assert data == expected_response


@pytest.mark.online
class TestTVDBSearchLookupAPI(object):
    config = 'tasks: {}'

    def test_tvdb_search_results(self, api_client):
        expected_response = {u'search_results': [{u'status': u'Continuing', u'network': u'The CW',
                                                  u'overview': u'Two brothers follow their father\'s footsteps as "hunters" fighting evil supernatural beings of many kinds including monsters, demons, and gods that roam the earth.',
                                                  u'tvdb_id': 78901, u'series_name': u'Supernatural',
                                                  u'first_aired': u'Tue, 13 Sep 2005 00:00:00 GMT',
                                                  u'banner': u'http://thetvdb.com/banners/graphical/78901-g45.jpg',
                                                  u'aliases': []}, {u'status': u'Ended', u'network': u'The CW',
                                                                    u'overview': u'Supernatural the Animation will not only remake the best episodes from the live-action version, but also depict original episodes. These original episodes will include prologues of the Winchester brothers\u2019 childhood, anime-only enemies, and episodes featuring secondary characters from the original series.',
                                                                    u'tvdb_id': 197001,
                                                                    u'series_name': u'Supernatural the Animation',
                                                                    u'first_aired': u'Wed, 12 Jan 2011 00:00:00 GMT',
                                                                    u'banner': u'http://thetvdb.com/banners/graphical/197001-g2.jpg',
                                                                    u'aliases': [u'Supernatural: The Animation']},
                                                 {u'status': u'Ended', u'network': u'BBC', u'overview': None,
                                                  u'tvdb_id': 79426, u'series_name': u'Supernatural Science',
                                                  u'first_aired': u'Thu, 09 Nov 2006 00:00:00 GMT',
                                                  u'banner': u'http://thetvdb.com/banners/graphical/z79426-g.jpg',
                                                  u'aliases': []}, {u'status': u'Ended', u'network': u'BBC One',
                                                                    u'overview': u'Supernatural is a British anthology television series that was produced by the BBC in 1977. The series consisted of 8 episodes and was broadcast on BBC1. In each episode, a different prospective member of the "Club of the Damned" would be required to tell a horror story, and their application for membership would be judged on how frightening the story was. ',
                                                                    u'tvdb_id': 74143,
                                                                    u'series_name': u'The Supernatural (1977)',
                                                                    u'first_aired': u'Wed, 01 Jun 1977 00:00:00 GMT',
                                                                    u'banner': None,
                                                                    u'aliases': [u'The Supernatural 1977']},
                                                 {u'status': u'Ended', u'network': u'BBC',
                                                  u'overview': u"When science fiction becomes science fact.\r\nThis groundbreaking series unravels the extra-sensory feats and near-paranormal powers of animals. It journeys to the outer limits of scientific knowledge to find a parallel animal universe where life exists in other realities and has powers that almost defy belief. Here sharks perceive human electric auras and dolphins use ultrasound to 'see' a human foetus in the womb. There are monkey herbalists, frogs that have mastered the art of cryogenics and lizards that walk on water or cry blood. \r\n\r\nSupernatural not only looks at animal hypnosis and the healing powers of fish and dolphins, it even explains weird phenomena such as animals foretelling earthquakes or forecasting the weather and fish that 'rain' from the sky.",
                                                  u'tvdb_id': 79432,
                                                  u'series_name': u'Supernatural The Unseen Powers of Animals',
                                                  u'first_aired': u'Tue, 30 Mar 1999 00:00:00 GMT',
                                                  u'banner': u'http://thetvdb.com/banners/graphical/z79432-g.jpg',
                                                  u'aliases': []}, {u'status': u'', u'network': u'The Weather Channel',
                                                                    u'overview': u'Weather-inspired legends in the U.S. are explored in this series',
                                                                    u'tvdb_id': 287236,
                                                                    u'series_name': u'American Super/Natural',
                                                                    u'first_aired': u'Sun, 05 Oct 2014 00:00:00 GMT',
                                                                    u'banner': u'http://thetvdb.com/banners/graphical/287236-g.jpg',
                                                                    u'aliases': []},
                                                 {u'status': u'Ended', u'network': u'Discovery',
                                                  u'overview': u'Does life end in death? Or does the soul wander from body to body? Are there such things as demons, ghosts or the devil? Following circumstantial research and in cooperation with top-calibre scholars, this series sheds light upon, unmasks and takes the magic from centuries-old superstition and also reports on breathtaking, super sensory experiences. It also shows if, and where, things that cannot be explained really do exist? The journey in search of the Supernatural leads to all six continents, to such fascinating spots as the holy Tibetan city, Lhasa and to the great universities of the world; to the secret archives of the CIA and the KGB, the Vatican, and to the most modern centres of nuclear research in the world. The result is a thrilling combination of contemporary history, scientific background reporting, and a touch of the pleasant shiver within the dark side of parapsychology.',
                                                  u'tvdb_id': 154401,
                                                  u'series_name': u'5th Dimension - Secrets of the Supernatural',
                                                  u'first_aired': u'Sat, 21 Jan 2006 00:00:00 GMT',
                                                  u'banner': u'http://thetvdb.com/banners/graphical/154401-g.jpg',
                                                  u'aliases': [u'5th Dimension  Secrets of the Supernatural']},
                                                 {u'status': u'Continuing', u'network': u'Destination America',
                                                  u'overview': u'Mysterious phenomena are explored using scientific techniques in this series.',
                                                  u'tvdb_id': 294240, u'series_name': u'True Supernatural',
                                                  u'first_aired': u'Wed, 08 Apr 2015 00:00:00 GMT',
                                                  u'banner': u'http://thetvdb.com/banners/text/294240.jpg',
                                                  u'aliases': []}, {u'status': u'Ended', u'network': u'TV Tokyo',
                                                                    u'overview': u'Half a year ago, the four members of a literature club, as well as the elementary school niece of their faculty adviser, were bestowed with supernatural powers. The boy in the club, Ando Jurai, became able to produce black flames. The girls acquired a variety of powerful abilities: Tomoyo could slow, speed, or stop time, Hatoko could control the five elements (earth, water, fire, wind, light), little Chifuyu could create things, and Sayumi could repair objects or heal living things. However, since they gained these powers, nothing has really changed in their everyday life. Why have they been given these powers in the first place? Will the heroic fantasy life they imagined these powers would bring ever actually arrive?',
                                                                    u'tvdb_id': 283937,
                                                                    u'series_name': u'When Supernatural Battles Became Commonplace',
                                                                    u'first_aired': u'Tue, 07 Oct 2014 00:00:00 GMT',
                                                                    u'banner': u'http://thetvdb.com/banners/graphical/283937-g.jpg',
                                                                    u'aliases': [
                                                                        u'Inou Battle wa Nichijou-kei no Naka de',
                                                                        u'Inou Battle Within Everyday Life',
                                                                        u'Inou-Battle in the Usually Daze',
                                                                        u'Inou-Battle in the Usually Daze.',
                                                                        u'Inou-Battle wa Nichijou-kei no Naka de']}]}

        rsp = api_client.get('/tvdb/search/?search_name=supernatural')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        assert data == expected_response

        expected_response = {
            u'search_results': [
                {u'status': u'Continuing',
                 u'network': u'HBO',
                 u'overview': u"Seven noble families fight for control of the mythical land of Westeros. "
                              u"Friction between the houses leads to full-scale war. All while a very ancient"
                              u" evil awakens in the farthest north. Amidst the war, a neglected military order "
                              u"of misfits, the Night's Watch, is all that stands between the realms of men and the "
                              u"icy horrors beyond.",
                 u'tvdb_id': 121361,
                 u'series_name': u'Game of Thrones',
                 u'first_aired': u'Sun, 17 Apr 2011 00:00:00 GMT',
                 u'banner': u'http://thetvdb.com/banners/graphical/121361-g19.jpg',
                 u'aliases': []}]}
        rsp = api_client.get('/tvdb/search/?imdb_id=tt0944947')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        assert data == expected_response

        expected_response = {
            u'search_results': [
                {u'status': u'Continuing',
                 u'network': u'The CW',
                 u'overview': u'After a particle accelerator causes a freak storm, CSI Investigator Barry Allen is '
                              u'struck by lightning and falls into a coma. Months later he awakens with the power '
                              u'of super speed, granting him the ability to move through Central City like an unseen '
                              u'guardian angel. Though initially excited by his newfound powers, Barry is shocked to '
                              u'discover he is not the only "meta-human" who was created in the wake of'
                              u' the accelerator explosion \u2013 and not everyone is using their new powers '
                              u'for good. Barry partners with S.T.A.R. Labs and dedicates his life to protect'
                              u' the innocent. For now, only a few close friends and associates know that Barry '
                              u'is literally the fastest man alive, but it won\'t be long before the world learns '
                              u'what Barry Allen has become... The Flash.',
                 u'tvdb_id': 279121, u'series_name': u'The Flash (2014)',
                 u'first_aired': u'Tue, 07 Oct 2014 00:00:00 GMT',
                 u'banner': u'http://thetvdb.com/banners/graphical/279121-g7.jpg',
                 u'aliases': []}]}
        rsp = api_client.get('/tvdb/search/?zap2it_id=EP01922936')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        assert data == expected_response
