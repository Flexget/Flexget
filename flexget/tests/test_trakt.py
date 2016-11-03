# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.manager import Session
from flexget.plugins.internal.api_trakt import ApiTrakt, TraktActor, TraktMovieSearchResult, TraktShowSearchResult
from flexget.plugins.internal.api_trakt import TraktShow

lookup_series = ApiTrakt.lookup_series


@pytest.mark.online
class TestTraktShowLookup(object):
    config = """
        templates:
          global:
            trakt_lookup: yes
            # Access a trakt field to cause lazy loading to occur
            set:
              afield: "{{tvdb_id}}{{trakt_ep_name}}"
        tasks:
          test:
            mock:
              - {title: 'House.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Doctor.Who.2005.S02E03.PDTV.XViD-FlexGet'}
            series:
              - House
              - Doctor Who 2005
          test_unknown_series:
            mock:
              - {title: 'Aoeu.Htns.S01E01.htvd'}
            series:
              - Aoeu Htns
          test_date:
            mock:
              - title: the daily show 2012-6-6
            series:
              - the daily show (with trevor noah)
          test_absolute:
            mock:
              - title: naruto 128
            series:
              - naruto
          test_search_result:
            mock:
              - {title: 'Shameless.2011.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Shameless.2011.S03E02.HDTV.XViD-FlexGet'}
            series:
              - Shameless (2011)
          test_search_success:
            mock:
              - {title: '11-22-63.S01E01.HDTV.XViD-FlexGet'}
            series:
              - 11-22-63
          test_alternate_language:
            mock:
              - {'title': 'Игра престолов (2011).s01e01.hdtv'}
            series:
              - Игра престолов
          test_lookup_translations:
            mock:
              - {title: 'Game.Of.Thrones.S01E02.HDTV.XViD-FlexGet'}
            series:
              - Game Of Thrones
    """

    def test_lookup_name(self, execute_task):
        """trakt: Test Lookup (ONLINE)"""
        task = execute_task('test')
        entry = task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['trakt_show_id'] == 1399, \
            'Trakt_ID should be 1339 is %s for %s' % (entry['trakt_show_id'], entry['series_name'])
        assert entry['trakt_series_status'] == 'ended', 'Series Status should be "ENDED" returned %s' \
                                                        % (entry['trakt_series_status'])

    def test_lookup(self, execute_task):
        """trakt: Test Lookup (ONLINE)"""
        task = execute_task('test')
        entry = task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['trakt_ep_name'] == 'Paternity', \
            '%s trakt_ep_name should be Paternity' % entry['title']
        assert entry['trakt_series_status'] == 'ended', \
            'runtime for %s is %s, should be "ended"' % (entry['title'], entry['trakt_series_status'])
        assert entry['afield'] == '73255Paternity', 'afield was not set correctly'
        assert task.find_entry(trakt_ep_name='School Reunion'), \
            'Failed imdb lookup Doctor Who 2005 S02E03'

    def test_unknown_series(self, execute_task):
        # Test an unknown series does not cause any exceptions
        task = execute_task('test_unknown_series')
        # Make sure it didn't make a false match
        entry = task.find_entry('accepted', title='Aoeu.Htns.S01E01.htvd')
        assert entry.get('tvdb_id') is None, 'should not have populated tvdb data'

    def test_search_results(self, execute_task):
        task = execute_task('test_search_result')
        entry = task.entries[0]
        print(entry['trakt_series_name'].lower())
        assert entry['trakt_series_name'].lower() == 'Shameless'.lower(), 'lookup failed'
        with Session() as session:
            assert task.entries[1]['trakt_series_name'].lower() == 'Shameless'.lower(), 'second lookup failed'

            assert len(session.query(TraktShowSearchResult).all()) == 1, 'should have added 1 show to search result'

            assert len(session.query(TraktShow).all()) == 1, 'should only have added one show to show table'
            assert session.query(TraktShow).first().title == 'Shameless', 'should have added Shameless and' \
                                                                          'not Shameless (2011)'
            # change the search query
            session.query(TraktShowSearchResult).update({'search': "shameless.s01e03.hdtv-flexget"})
            session.commit()

            lookupargs = {'title': "Shameless.S01E03.HDTV-FlexGet"}
            series = ApiTrakt.lookup_series(**lookupargs)

            assert series.tvdb_id == entry['tvdb_id'], 'tvdb id should be the same as the first entry'
            assert series.id == entry['trakt_show_id'], 'trakt id should be the same as the first entry'
            assert series.title.lower() == entry['trakt_series_name'].lower(), 'series name should match first entry'

    def test_search_success(self, execute_task):
        task = execute_task('test_search_success')
        entry = task.find_entry('accepted', title='11-22-63.S01E01.HDTV.XViD-FlexGet')
        assert entry.get('trakt_show_id') == 102771, 'Should have returned the correct trakt id'

    def test_date(self, execute_task):
        task = execute_task('test_date')
        entry = task.find_entry(title='the daily show 2012-6-6')
        # Make sure show data got populated
        assert entry.get('trakt_show_id') == 2211, 'should have populated trakt show data'
        # We don't support lookup by date at the moment, make sure there isn't a false positive
        if entry.get('trakt_episode_id') == 173423:
            assert False, 'We support trakt episode lookup by date now? Great! Change this test.'
        else:
            assert entry.get('trakt_episode_id') is None, 'false positive for episode match, we don\'t ' \
                                                          'support lookup by date'

    def test_absolute(self, execute_task):
        task = execute_task('test_absolute')
        entry = task.find_entry(title='naruto 128')
        # Make sure show data got populated
        assert entry.get('trakt_show_id') == 46003, 'should have populated trakt show data'
        # We don't support lookup by absolute number at the moment, make sure there isn't a false positive
        if entry.get('trakt_show_id') == 916040:
            assert False, 'We support trakt episode lookup by absolute number now? Great! Change this test.'
        else:
            assert entry.get('trakt_episode_id') is None, 'false positive for episode match, we don\'t ' \
                                                          'support lookup by absolute number'

    def test_lookup_actors(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['series_name'] == 'House', 'series lookup failed'
        assert entry['trakt_actors']['297390']['name'] == 'Hugh Laurie', 'trakt id mapping failed'
        assert entry['trakt_actors']['297390']['imdb_id'] == 'nm0491402', 'fetching imdb id for actor failed'
        assert entry['trakt_actors']['297390']['tmdb_id'] == '41419', 'fetching tmdb id for actor failed'
        with Session() as session:
            actor = session.query(TraktActor).filter(TraktActor.name == 'Hugh Laurie').first()
            assert actor is not None, 'adding actor to actors table failed'
            assert actor.imdb == 'nm0491402', 'saving imdb_id for actors in table failed'
            assert str(actor.id) == '297390', 'saving trakt_id for actors in table failed'
            assert str(actor.tmdb) == '41419', 'saving tmdb_id for actors table failed'

    def test_lookup_translations(self, execute_task):
        task = execute_task('test_lookup_translations')
        assert len(task.entries) == 1
        entry = task.entries[0]

        assert entry['series_name'] == 'Game Of Thrones', 'series lookup failed'
        assert len(entry['trakt_translations']) > 0


@pytest.mark.online
class TestTraktList(object):
    config = """
        tasks:
          test_trakt_movies:
            trakt_list:
              username: flexgettest
              list: watchlist
              type: movies
    """

    def test_trakt_movies(self, execute_task):
        task = execute_task('test_trakt_movies')
        assert len(task.entries) == 1
        entry = task.entries[0]
        assert entry['title'] == '12 Angry Men (1957)'
        assert entry['movie_name'] == '12 Angry Men'
        assert entry['movie_year'] == 1957
        assert entry['imdb_id'] == 'tt0050083'


@pytest.mark.online
class TestTraktWatchedAndCollected(object):
    config = """
        tasks:
          test_trakt_watched:
            metainfo_series: yes
            trakt_lookup:
                username: flexgettest
            mock:
              - title: Hawaii.Five-0.S04E13.HDTV-FlexGet
              - title: The.Flash.2014.S01E10.HDTV-FlexGet
            if:
              - trakt_watched: accept
          test_trakt_collected:
            metainfo_series: yes
            trakt_lookup:
               username: flexgettest
            mock:
              - title: Homeland.2011.S02E01.HDTV-FlexGet
              - title: The.Flash.2014.S01E10.HDTV-FlexGet
            if:
              - trakt_collected: accept
          test_trakt_watched_movie:
            trakt_lookup:
                username: flexgettest
            mock:
              - title: Inside.Out.2015.1080p.BDRip-FlexGet
              - title: The.Matrix.1999.1080p.BDRip-FlexGet
            if:
              - trakt_watched: accept
          test_trakt_collected_movie:
            trakt_lookup:
              username: flexgettest
            mock:
              - title: Inside.Out.2015.1080p.BDRip-FlexGet
              - title: The.Matrix.1999.1080p.BDRip-FlexGet
            if:
              - trakt_collected: accept
          test_trakt_show_collected_progress:
            disable: builtins
            trakt_lookup:
              username: flexgettest
            trakt_list:
              username: flexgettest
              list: test
              type: shows
            if:
              - trakt_collected: accept
          test_trakt_show_watched_progress:
            disable: builtins
            trakt_lookup:
              username: flexgettest
            trakt_list:
              username: flexgettest
              list: test
              type: shows
            if:
              - trakt_watched: accept
    """

    def test_trakt_watched_lookup(self, execute_task):
        task = execute_task('test_trakt_watched')
        assert len(task.accepted) == 1, 'Episode should have been marked as watched and accepted'
        entry = task.accepted[0]
        assert entry['title'] == 'Hawaii.Five-0.S04E13.HDTV-FlexGet', 'title was not accepted?'
        assert entry['series_name'] == 'Hawaii Five-0', 'wrong series was returned by lookup'
        assert entry['trakt_watched'] == True, 'episode should be marked as watched'

    def test_trakt_collected_lookup(self, execute_task):
        task = execute_task('test_trakt_collected')
        assert len(task.accepted) == 1, 'Episode should have been marked as collected and accepted'
        entry = task.accepted[0]
        assert entry['title'] == 'Homeland.2011.S02E01.HDTV-FlexGet', 'title was not accepted?'
        assert entry['series_name'] == 'Homeland 2011', 'wrong series was returned by lookup'
        assert entry['trakt_collected'] == True, 'episode should be marked as collected'

    def test_trakt_watched_movie_lookup(self, execute_task):
        task = execute_task('test_trakt_watched_movie')
        assert len(task.accepted) == 1, 'Movie should have been accepted as it is watched on Trakt profile'
        entry = task.accepted[0]
        assert entry['title'] == 'Inside.Out.2015.1080p.BDRip-FlexGet', 'title was not accepted?'
        assert entry['movie_name'] == 'Inside Out', 'wrong movie name'
        assert entry['trakt_watched'] == True, 'movie should be marked as watched'

    def test_trakt_collected_movie_lookup(self, execute_task):
        task = execute_task('test_trakt_collected_movie')
        assert len(task.accepted) == 1, 'Movie should have been accepted as it is collected on Trakt profile'
        entry = task.accepted[0]
        assert entry['title'] == 'Inside.Out.2015.1080p.BDRip-FlexGet', 'title was not accepted?'
        assert entry['movie_name'] == 'Inside Out', 'wrong movie name'
        assert entry['trakt_collected'] == True, 'movie should be marked as collected'

    def test_trakt_show_watched_progress(self, execute_task):
        task = execute_task('test_trakt_show_watched_progress')
        assert len(task.accepted) == 1, 'One show should have been accepted as it is watched on Trakt profile'
        entry = task.accepted[0]
        assert entry['trakt_series_name'] == 'Chuck', 'wrong series was accepted'
        assert entry['trakt_watched'] == True, 'the whole series should be marked as watched'

    def test_trakt_show_collected_progress(self, execute_task):
        task = execute_task('test_trakt_show_collected_progress')
        assert len(task.accepted) == 1, 'One show should have been accepted as it is collected on Trakt profile'
        entry = task.accepted[0]
        assert entry['trakt_series_name'] == 'White Collar', 'wrong series was accepted'
        assert entry['trakt_collected'] == True, 'the whole series should be marked as collected'


@pytest.mark.online
class TestTraktMovieLookup(object):
    config = """
        templates:
          global:
            trakt_lookup: yes
        tasks:
          test_lookup_sources:
            mock:
            - title: trakt id
              trakt_movie_id: 481
            - title: tmdb id
              tmdb_id: 603
            - title: imdb id
              imdb_id: tt0133093
            - title: slug
              trakt_movie_slug: the-matrix-1999
            - title: movie_name and movie_year
              movie_name: The Matrix
              movie_year: 1999
            - title: The Matrix (1999)
          test_lookup_actors:
            mock:
            - title: The Matrix (1999)
          test_search_results:
            mock:
            - title: harry.potter.and.the.philosopher's.stone.720p.hdtv-flexget
          test_search_results2:
            mock:
            - title: harry.potter.and.the.philosopher's.stone
          test_lookup_translations:
            mock:
            - title: The Matrix Reloaded (2003)
    """

    def test_lookup_sources(self, execute_task):
        task = execute_task('test_lookup_sources')
        for e in task.all_entries:
            assert e['movie_name'] == 'The Matrix', 'looking up based on %s failed' % e['title']

    def test_search_results(self, execute_task):
        task = execute_task('test_search_results')
        entry = task.entries[0]
        assert entry['movie_name'].lower() == 'Harry Potter and The Philosopher\'s Stone'.lower(), 'lookup failed'
        with Session() as session:
            assert len(session.query(TraktMovieSearchResult).all()) == 1, 'should have added one movie to search result'

            # change the search query
            session.query(TraktMovieSearchResult).update({'search': "harry.potter.and.the.philosopher's"})
            session.commit()

            lookupargs = {'title': "harry.potter.and.the.philosopher's"}
            movie = ApiTrakt.lookup_movie(**lookupargs)

            assert movie.imdb_id == entry['imdb_id']
            assert movie.title.lower() == entry['movie_name'].lower()

    def test_lookup_actors(self, execute_task):
        task = execute_task('test_lookup_actors')
        assert len(task.entries) == 1
        entry = task.entries[0]
        actors = ['Keanu Reeves',
                  'Laurence Fishburne',
                  'Carrie-Anne Moss',
                  'Hugo Weaving',
                  'Gloria Foster',
                  'Joe Pantoliano',
                  'Marcus Chong',
                  'Julian Arahanga',
                  'Matt Doran',
                  'Belinda McClory',
                  'Anthony Ray Parker',
                  'Paul Goddard',
                  'Robert Taylor',
                  'David Aston',
                  'Marc Aden',
                  'Ada Nicodemou',
                  'Deni Gordon',
                  'Rowan Witt',
                  'Bill Young',
                  'Eleanor Witt',
                  'Tamara Brown',
                  'Janaya Pender',
                  'Adryn White',
                  'Natalie Tjen',
                  'David O\'Connor',
                  'Jeremy Ball',
                  'Fiona Johnson',
                  'Harry Lawrence',
                  'Steve Dodd',
                  'Luke Quinton',
                  'Lawrence Woodward',
                  'Michael Butcher',
                  'Bernard Ledger',
                  'Robert Simper',
                  'Chris Pattinson',
                  'Nigel Harbach',
                  'Rana Morrison']
        trakt_actors = list(entry['trakt_actors'].values())
        trakt_actors = [trakt_actor['name'] for trakt_actor in trakt_actors]
        assert entry['movie_name'] == 'The Matrix', 'movie lookup failed'
        assert set(trakt_actors) == set(actors), 'looking up actors for %s failed' % entry.get('title')
        assert entry['trakt_actors']['7134']['name'] == 'Keanu Reeves', 'trakt id mapping failed'
        assert entry['trakt_actors']['7134']['imdb_id'] == 'nm0000206', 'fetching imdb id for actor failed'
        assert entry['trakt_actors']['7134']['tmdb_id'] == '6384', 'fetching tmdb id for actor failed'
        with Session() as session:
            actor = session.query(TraktActor).filter(TraktActor.name == 'Keanu Reeves').first()
            assert actor is not None, 'adding actor to actors table failed'
            assert actor.imdb == 'nm0000206', 'saving imdb_id for actors in table failed'
            assert str(actor.id) == '7134', 'saving trakt_id for actors in table failed'
            assert str(actor.tmdb) == '6384', 'saving tmdb_id for actors table failed'

    def test_lookup_translations(self, execute_task):
        translations = {
            "bg": {
                "overview": "Нео вече разполага с по-голям контрол върху свръхестествените си сили, след като Цион пада под обсадата на Армията на Машините. Само часове делят последният човешки анклав на Земята от 250,000 стражи, програмирани да унищожат човечеството. Но за гражданите на Зион, насърчавани от обещанието на Морфей, че Един ще изпълни Пророчеството на Оракула и ще донесе победа във войната с Машините, всички надежди и очаквания са съсредоточени в Нео. А той се сблъсква с объркващи видения, докато търси посоката, в която да действа.",
                "tagline": "",
                "title": "Матрицата: Презареждане"
            },
            "ca": {
                "overview": "Thomas \"Neo\" Anderson va prendre una costosa decisió quan va decidir fer la pregunta que Morfeu i Trinity havien formulat abans que ell. Cercar i acceptar la veritat. Alliberar la seva ment de Matrix. Ara, Neo adquireix un major domini dels seus extraordinaris poders mentre Sió cau assetjada per l'Exèrcit de les Màquines. Només una qüestió d'hores separa a l'últim enclavament humà a la Terra de 250.000 Sentinelles programats per destruir a la humanitat. Però els ciutadans de Sió, animats per la convicció de Morfeu que l'Elegit farà realitat la Profecia de l'Oracle i posarà fi a la guerra amb les Màquines, posen totes les seves esperances i expectatives en Neo, que es troba bloquejat per visions inquietants mentre cerca quines mesures prendre.",
                "tagline": "",
                "title": "Matrix Reloaded"
            },
            "cs": {
                "overview": "Druhé pokračování trilogie Matrix nás opět zavede do temného světa budoucnosti ovládaného stroji. Lidstvo stále trpí v otroctví virtuální reality, z kterého ho může osvobodit jen Vyvolený. Nea s Morpheem a Trinity čeká boj s armádou strojů a jejich arzenálem počítačově nelidských schopností a zbraní. Pokud ale chtějí zastavit zotročování lidstva, není jiná možnost než boj na život a na smrt. Nezbývá jim nic jiného než proniknout hluboko do struktur Matrixu a během 72 hodin objevit a zlikvidovat centrum Zion i s jeho pomocnými jednotkami. Neo ve svých temných nočních můrách vidí, že Trinitiným osudem je smrt. Dokáže se znovu vzepřít osudu a svou mocí zastavit nekonečné útoky strojů?",
                "tagline": "Osvoboď svoji mysl.",
                "title": "Matrix Reloaded"
            },
            "da": {
                "overview": "250.000 maskiner er ved at bore sig gennem jorden ind til Zion og inden 72 timer når de byen og vil udslette befolkningen. Neo må have sine mægtige kræfter i spil i en fart og han møder oraklet.  Agent Smith har fået storhedsvanvid og kører sit eget løb og samtidig forudser Neo i drømme, hvordan hans elskede Trinity dør - en skæbne han for alt i verden må redde hende fra.",
                "tagline": "",
                "title": "The Matrix Reloaded"
            },
            "de": {
                "overview": "Die Wächter schwärmen aus. Smith klont sich. Neo fliegt... aber vielleicht kann selbst der Auserwählte mit seinen atemberaubenden neuen Fähigkeiten den Angriff der Maschinen nicht mehr aufhalten. Neo. Morpheus, Trinity. Zurück im spannenden zweiten Kapitel der Matrix-Trilogie treffen sie auf außergewöhnliche Verbündete: Gemeinsam bekämpfen sie ihre Gegner, die sich klonen, durch Upgrades immer stärker werden und die letzte Festung der Menschheit belagern.",
                "tagline": "Befreie Deinen Geist.",
                "title": "Matrix Reloaded"
            },
            "el": {
                "overview": "Στο THE MATRIX RELOADED οι μαχητές της ελευθερίας, ο Νίο, η Τρίνιτι κι ο Μορφέας, συνεχίζουν τον αγώνα τους ενάντια στο Στρατό των Μηχανών, προβάλλοντας εξαιρετικές ικανότητες μάχης κι όπλων ενάντια στις συστηματικές δυνάμεις καταστολής και εκμετάλλευσης της ανθρώπινης φυλής. Στην προσπάθειά τους να σώσουν τους ανθρώπους που απειλούνται, «εντάσσονται» ακόμα περισσότερο μέσα στο MATRIX και διαδραματίζουν καθοριστικό ρόλο στην έκβαση της μοίρας των ανθρώπων.  Υπάρχουν δύο πραγματικότητες: μία που αποτελείται από την καθημερινή μας ζωή - και μία που συνθλίβει αυτό που ξέρουμε μέχρι σήμερα. Η πρώτη είναι ένα όνειρο. Η άλλη είναι το Μatrix. Ο Νίο (Κιάνου Ριβς), ο Μορφέας (Λόρενς Φίσμπερν) και η Τρίνιτι (Κάρι Αν Μος) μας \"ξυπνάνε\" μέσα στον αφόρητα πραγματικό και σκοτεινό κόσμο του Matrix. Μαζί αγωνίζονται πάλι για να σώσουν κι άλλους \"ελεύθερους\" ανθρώπους που προσπαθούν να επιβιώσουν έναντι των μηχανών, οι οποίες κυριαρχούν.",
                "tagline": "",
                "title": "The Matrix Reloaded"
            },
            "en": {
                "overview": "Six months after the events depicted in The Matrix, Neo has proved to be a good omen for the free humans, as more and more humans are being freed from the matrix and brought to Zion, the one and only stronghold of the Resistance.  Neo himself has discovered his superpowers including super speed, ability to see the codes of the things inside the matrix and a certain degree of pre-cognition. But a nasty piece of news hits the human resistance: 250,000 machine sentinels are digging to Zion and would reach them in 72 hours. As Zion prepares for the ultimate war, Neo, Morpheus and Trinity are advised by the Oracle to find the Keymaker who would help them reach the Source.  Meanwhile Neo's recurrent dreams depicting Trinity's death have got him worried and as if it was not enough, Agent Smith has somehow escaped deletion, has become more powerful than before and has fixed Neo as his next target.",
                "tagline": "Free your mind.",
                "title": "The Matrix Reloaded"
            },
            "es": {
                "overview": "Las máquinas avanzan imparables hacia Zion en su afán por destruir a toda la humanidad y todas las naves se preparan para la dura batalla. Neo junto con Morfeo y Trinity buscan el camino del elegido dentro de Matrix para vencer a las máquinas y se encuentran con dificultades inesperadas: el agente Smith ha vuelto, y no solo eso, otros programas dentro de Matrix intentarán acabar con su misión. Mientras tanto Neo se tendrá que adaptar a la vida real y a la fama de ser el elegido.",
                "tagline": "Abre tu mente",
                "title": "Matrix Reloaded"
            },
            "fa": {
                "overview": "نئو و رهبران شورش تخمین میزنند که حدود ۷۲ ساعت تا حمله ۲۵۰ هزار ماشین به صهیون، وقت دارند. در همین زمان نئو باید تصمیم بگیرد که چگونه ترینیتی را از سرنوشت تاریکی که در رویا برایش دیده، نجات دهد.",
                "tagline": "",
                "title": "ماتریکس: بارگذاری مجدد"
            },
            "fi": {
                "overview": "Koneiden armeija valmistautuu hyökkäykseen. Smith-klooneja on kaikkialla. Neo lentää…mutta ehkäpä edes Valitun uskomattomat voimat eivät ole tarpeeksi pysäyttämään metallihirviöiden etenemistä. Uudet liittolaiset liittyvät ihmisten riveihin taistelussa vastustajia vastaan, joiden lukumäärä on lisääntynyt ja taidot päivitetty sitten viime näkemän.",
                "tagline": "",
                "title": "Matrix Reloaded"
            },
            "fr": {
                "overview": "Neo apprend à mieux contrôler ses dons naturels, alors même que Sion s'apprête à tomber sous l'assaut de l'Armée des Machines. D'ici quelques heures, 250 000 Sentinelles programmées pour anéantir notre espèce envahiront la dernière enclave humaine de la Terre. Mais Morpheus galvanise les citoyens de Sion en leur rappelant la Parole de l'Oracle : il est encore temps pour l’Élu d'arrêter la guerre contre les Machines. Tous les espoirs se reportent dès lors sur Neo. Au long de sa périlleuse plongée au sein de la Matrix et de sa propre destinée, ce dernier sera confronté à une résistance croissante, une vérité encore plus aveuglante, un choix encore plus douloureux que tout ce qu'il avait jamais imaginé.",
                "tagline": "Libérez votre esprit.",
                "title": "Matrix Reloaded"
            },
            "he": {
                "overview": "אחד משוברי הקופות הגדולים בכל הזמנים. כשישה חודשים אחרי ה-\"מטריקס\" המקורי נפתח החלק השני של הטרילוגיה ובה יותר ויותר אנשים משתחררים ומגלים את העולם האמיתי. אך במקביל, צבא המשוכפלים עומד להשתלט על המבצר האנושי האחרון, וניאו, מורפיאוס, טריניטי ושותפיהם מנסים למצוא פיתרון, רגע לפני הסוף הסופי בהחלט. מהר יותר, חזק יותר, מעופף יותר.",
                "tagline": "תנו למחשבותיכם חופש...",
                "title": "מטריקס רילודד"
            },
            "hu": {
                "overview": "Mi történne, ha a prófécia igaznak bizonyulna? Mi lenne, ha holnap véget érne a harc? Thomas \"Neo\" Anderson (Keanu Reeves) úgy dönt, szembenéz a kérdéssel, amelyet Morpheus (Laurence Fishburne) és Trinity (Carrie-Anne Moss) sugallt neki. Elindul, hogy felkutassa és megismerje az igazságot, és értelmét kiszabadítsa a Mátrix rabságából.A trilógia második epizódjában Neo elhatározza, hogy a benne rejlő erőket még jobban uralma alá hajtja. A gépek hadserege támadást indít Zion városa ellen. Órák kérdése csupán, hogy a Föld utolsó ember uralta területét is elfoglalják az emberiség elpusztítására beprogramozott gépek. Morpheusnak azonban sikerül felráznia Zion polgárait, és meggyőznie őket arról, hogy be fog teljesülni a jóslat, és a Kiválasztott véget fog vetni a gépekkel vívott háborúnak. Szerelmükkel és egymásba vetett hitükkel felvértezve Neo és Trinity úgy döntenek, visszatérnek a Mátrixba, hogy különleges képességeiket és fegyvereiket latba vetve szembeszálljanak a zsarnoksággal.",
                "tagline": "Szabadítsd fel a tudatod.",
                "title": "Mátrix - Újratöltve"
            },
            "it": {
                "overview": "Ora Neo controlla perfettamente i suoi straordinari poteri e Zion è assediata dall'Esercito delle Macchine. Solo poche ore separano l'ultima enclave umana sulla Terra da 250.000 Sentinelle programmate per distruggere il genere umano. Ma i cittadini di Zion, incoraggiati dalla convinzione di Morpheus che L'Eletto adempierà la Profezia dell'Oracolo e metterà fine alla guerra con le Macchine, puntano tutte le loro speranze su Neo, che si ritrova bloccato da visioni sconvolgenti. Resi più forti dall'amore e dalla fiducia che li lega, Neo e Trinity scelgono di tornare in Matrix con Morpheus e di lottare contro le forze della repressione e dello sfruttamento. Ma esistono ancora figure potenti dentro Matrix che si oppongono all'artificio della scelta, e si sottraggono alla responsabilità che comporta, poiché si cibano delle verità emotive degli altri.",
                "tagline": "Libera la tua mente",
                "title": "Matrix reloaded"
            },
            "ja": {
                "overview": "人類の最期の砦「ザイオン」に残されたのは72時間。それを過ぎれば25万のセンチネルに襲われるだろう。しかしモーフィアスの信念は堅い。オラクルによればネオがこの戦争に終止符を打つ。一方のネオはヒントを得るためオラクルに会いに行く。",
                "tagline": "",
                "title": "マトリックス リローデッド"
            },
            "ko": {
                "overview": u"'\uc2dc\uc628'\uc740 \uc13c\ud2f0\ub12c\uc774\ub77c\ub294 \uae30\uacc4\uad70\ub2e8\uc5d0\uac8c \uc7a5\uc545\ub420 \uc704\uae30\uc5d0 \ucc98\ud558\uace0, \uc790\uc2e0\uc758 \ub2a5\ub825\uc5d0 \ub300\ud55c \ub354 \ud070 \ud1b5\uc81c\ub825\uc744 \uac16\uac8c \ub41c \ub124\uc624\ub294 \uc778\ub958\uc758 \uad6c\uc6d0\uc744 \uc704\ud574 \ud2b8\ub9ac\ub2c8\ud2f0, \ubaa8\ud53c\uc5b4\uc2a4(\ub85c\ub80c\uc2a4 \ud53c\uc26c\ubc88)\uc640 \ud568\uaed8 \uc2dc\uc2a4\ud15c\uc5d0 \ub9de\uc11c\uac8c \ub41c\ub2e4. '\ub9e4\ud2b8\ub9ad\uc2a4'\uc758 \ub0b4\ubd80 \uad6c\uc870\ub85c \uae4a\uc774 \ub4e4\uc5b4\uac08\uc218\ub85d, \uc778\ub958\uc758 \uc6b4\uba85\uc744 \uc88c\uc6b0\ud560 \uc790\uc2e0\uc758 \uc5ed\ud560\uc5d0 \ub208 \ub5a0\uac00\ub358 \ub124\uc624\ub294 '\uc124\uacc4\uc790'\ub97c \ub9cc\ub098 \uc790\uc2e0\uc758 \uc874\uc7ac\uac00 \uc124\uacc4\uc790\uc5d0 \uc758\ud574 \ub9cc\ub4e4\uc5b4\uc9c4 \ud1b5\uc81c \uc2dc\uc2a4\ud15c\uc5d0 \ubd88\uacfc\ud558\ub2e4\ub294 \ucda9\uaca9\uc801\uc778 \uc9c4\uc2e4\uc5d0 \uc9c1\uba74\ud55c\ub2e4. \uadf8\ub9ac\uace0 '\uc0ac\ub791\uc778\uac00, \uc778\ub958\uc758 \uad6c\uc6d0\uc778\uac00!'\ub77c\ub294 \ubd88\uac00\ub2a5\uc5d0 \uac00\uae4c\uc6b4 \uc120\ud0dd\uc744 \uac15\uc694 \ubc1b\ub294 \ub124\uc624. \ub458 \uc911 \ud558\ub098\ub294 \ud3ec\uae30\ud574\uc57c \ud55c\ub2e4!",
                "tagline": "\ubb34\uc5c7\uc744 \uc0c1\uc0c1\ud558\ub4e0 \uadf8 \uc774\uc0c1\uc744 \ubcf4\uac8c \ub420 \uac83\uc774\ub2e4!",
                "title": "매트릭스 2 - 리로디드"
            },
            "nl": {
                "overview": "De machines hebben de locatie van Zion, de laatste menselijke stad, gevonden. De enige hoop voor de rebellen is The Keymaker, een man met toegang tot alle deuren naar de machinewereld. Hij wordt echter bewaakt door The Twins, een gedreadlocked duo dat kan verdwijnen en verschijnen als geesten. Agent Smith kan zich inmiddels als een virus in The Matrix vermenigvuldigen, wat de zoektocht voor Neo, Trinity en Morpheus bemoeilijkt.",
                "tagline": "",
                "title": "The Matrix Reloaded"
            },
            "pl": {
                "overview": "Kontynuacja kultowego \"Matrixa\". \"Matrix Reaktywacja\" zaczyna się w momencie, w którym kończyła się pierwsza część. Maszyny dokonały brzemiennego w skutkach odkrycia: poznały lokalizację Zion, ostatniego miasta ludzi, ukrytego w pobliżu jądra Ziemi. Za 72 godziny tysiące Strażników - kałamarnicowatych maszyn znanych z pierwszej części - przebiją się do miasta. Jedyną nadzieją ludzi jest odnalezienie tajemniczej postaci, znanej jako Twórca Kluczy, chronionej przez parę uzbrojonych w noże Bliźniaków, nienaturalnie białych zabójców, potrafiących znikać i pojawiać się jak duchy.",
                "tagline": "Uwolnij się zanim zacznie się rewolucja!",
                "title": "Matrix Reaktywacja"
            },
            "pt": {
                "overview": "Após derrotar as máquinas em seu combate inicial, Neo (Keanu Reeves) ainda vive na Nabuconodosor ao lado de Morpheus (Laurence Fishburne), Trinity (Carrie-Anne Moss) e Link (Harold Perrineau Jr.), o novo tripulante da nave. As máquinas estão realizando uma grande ofensiva contra Zion, onde 250 mil máquinas estão escavando rumo à cidade e podem alcançá-la em poucos dias. A Nabucodonosor é convocada para retornar a Zion, para participar da reunião que definirá o contra-ataque humano às máquinas. Entretanto, um recado enviado pelo Oráculo (Gloria Foster) faz com que a nave parta novamente, levando Neo de volta à matrix. Lá ele descobre que precisa encontrar o Chaveiro (Randall Duk Kim), um ser que possui a chave para todos os caminhos da matrix e que é mantido como prisioneiro por Merovingian (Lambert Wilson) e sua esposa, Persephone (Monica Bellucci).",
                "tagline": "Liberte sua mente.",
                "title": "The Matrix Reloaded"
            },
            "ro": {
                "overview": "",
                "tagline": "Eliberează-ți mintea.",
                "title": "Matricea: Reîncărcată"
            },
            "ru": {
                "overview": "Борцы за свободу Нео, Тринити и Морфеус продолжают руководить восстанием людей против Армии Машин. Для уничтожения системы репрессий и эксплуатации они вынуждены прибегнуть не только к арсеналу превосходного оружия, но и к своим выдающимся навыкам.Участие в миссии по спасению человеческой расы от ее полного истребления приносит им более глубокое понимание конструкции Матрицы и осознание центральной роли Нео в судьбе человечества.",
                "tagline": "Одни машины помогают нам жить, другие – пытаются нас убить",
                "title": "Матрица: Перезагрузка"
            },
            "sk": {
                "overview": "Pokracovanie kultoveho sci-fi, ktore redefinovalo zaner akcneho filmu a ziskalo 4 Oskarov, nas opat zavedie do temneho sveta buducnosti. Ludstvo nadalej trpi v otroctve virtualnej reality, z ktorej ho moze oslobodit len vestbou predpovedany Vyvoleny. Novodoby spasitel Neo (Keanu Reeves) musi v druhej casti celit novym protivnikom - su nimi Dvojcata, nemilosrdni zabijaci, ktory dokazu menit Matrix a podriadovat ho svojej voly rovnako ako Neo. Okrem nich mu ide po krku aj agent Smith, ktory sa oddelil od Matrixu a teraz Nea prenasleduje na vlastnu past. Navyse ako virus dokaze naklonovat sam seba, takze Neo bude v jednej z vrcholnych scen filmu celit stovkam identickych agentov. Medzitym sa Trinity a Morpheus snazia zachranit tajomneho Kluciara, ktory dokaze otvorit kazde dvere v Matrixe a je dolezitou zbranou ludi v boji proti strojom. Aj medzi robotmi prebieha boj o nadvladu nad virtualnou realitou. Vsetky udalosti vedu k velkej vojne ludi proti strojom, ktory vypukne v tretej casti.",
                "tagline": "",
                "title": "Matrix Reloaded"
            },
            "sv": {
                "overview": "Neo uppskattar att han har ungefär 72 timmar på sig att förstöra de 250.000 destruktiva sonder han vet är utskickade. Under tiden måste han också bestämma sig för hur han ska rädda Trinity från det mörka öde han drömmer att hon ska drabbas av.",
                "tagline": "",
                "title": "Matrix Reloaded"
            },
            "th": {
                "overview": "",
                "tagline": "",
                "title": "สงครามมนุษย์เหนือโลก"
            },
            "tr": {
                "overview": "Neo ve Zion'un diğer isyancıları, Matrix'i dönüştürme çalışmalarına başlıyor. Neo'nun kendi gücünün ve misyonunun iyice farkına vardığı noktadan başlıyoruz filme. İlk filmde kendisini ve yoldaşlarını ajanların elinden kurtaran Neo, ikinci filmde bütün bir Zion şehrini ve sakinlerini kanatları altına almaya çalışacak. Bunun için de, ulaşmak son derece güç olsa da, Anahtarcı'yı bulmaları gerekiyor. Bu durum ise düşmanlarına yenilerini de katacaktır. Kendisini kopyalayıp, kopyalarından bir ordu hazırlayan Ajan Smith'e İkizler de katılır. The Matrix Reloaded'da, direnmeyi sürdüren tek insan kolonisi olan Zion'un kapıları seyircilere açılıyor. Fakat açılan kapılarından girmeye çalışan başkaları da olacaktır!..",
                "tagline": "",
                "title": "Matrix Reloaded"
            },
            "uk": {
                "overview": u'\u041d\u0435\u043e, \u041c\u043e\u0440\u0444\u0435\u0439 \u0442\u0430 \u0422\u0440\u0456\u043d\u0456\u0442\u0456 \u043d\u0430\u043c\u0430\u0433\u0430\u044e\u0442\u044c\u0441\u044f \u0437\u0430\u0445\u0438\u0441\u0442\u0438\u0442\u0438 \u043f\u0456\u0434\u0437\u0435\u043c\u043d\u0435 \u043c\u0456\u0441\u0442\u043e \u0417\u0456\u043e\u043d - \u043e\u0441\u0442\u0430\u043d\u043d\u044e \u0441\u0445\u043e\u0432\u0430\u043d\u043a\u0443 \u043b\u044e\u0434\u0435\u0439,  \u043f\u0440\u043e \u0456\u0441\u043d\u0443\u0432\u0430\u043d\u043d\u044f \u044f\u043a\u043e\u0457 \u043d\u0430\u0440\u0435\u0448\u0442\u0456 \u0434\u0456\u0437\u043d\u0430\u043b\u0438\u0441\u044c \u0431\u0435\u0437\u0436\u0430\u043b\u0456\u0441\u043d\u0456 \u043c\u0430\u0448\u0438\u043d\u0438. \u0414\u043b\u044f \u0446\u044c\u043e\u0433\u043e \u0433\u0435\u0440\u043e\u044f\u043c \u043f\u043e\u0442\u0440\u0456\u0431\u043d\u043e \u043f\u0440\u043e\u043d\u0438\u043a\u043d\u0443\u0442\u0438 \u0443 \u0441\u0432\u0456\u0442 \u041c\u0430\u0442\u0440\u0438\u0446\u0456 \u0456 \u043f\u0435\u0440\u0435\u0437\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0438\u0442\u0438 \u0457\u0457.',
                "tagline": "\u041f\u0435\u0440\u0435\u0437\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0435\u043d\u043d\u044f \u0434\u043e \u043f\u043e\u0447\u0430\u0442\u043a\u0443 \u0440\u0435\u0432\u043e\u043b\u044e\u0446\u0456\u0457",
                "title": "Матриця: Перезавантаження"
            },
            "zh": {
                "overview": "上一部结尾，尼奥（基奴李维斯 饰）终于意识到自己的能力和使命，中弹复活后，变成了无所不能的“救世主”，他和女友崔妮蒂（凯莉·安·摩丝 饰），舰长墨菲斯（劳伦斯·菲什伯恩 饰）回到了人类的基地锡安，受到人们的热烈欢迎。此时，“母体”决定先下手为强，派出了两万五千只电子乌贼攻击锡安基地；墨菲斯、尼奥和崔妮蒂则再次进入“母体”，寻找“制钥者”，准备从内部破坏；而本该被尼奥消灭的特勤史密斯似乎出了点问题，脱离了“母体”的控制，拥有可怕的复制能力，阻碍尼奥他们的行动....",
                "tagline": "",
                "title": "黑客帝国2：重装上阵"
            }
        }

        task = execute_task('test_lookup_translations')
        assert len(task.entries) == 1
        entry = task.entries[0]

        assert entry['movie_name'] == 'The Matrix Reloaded', 'movie lookup failed'
        assert entry['trakt_translations'] == translations


@pytest.mark.online
class TestTraktUnicodeLookup(object):
    config = """
        templates:
          global:
            trakt_lookup: yes
        tasks:
          test_unicode:
            disable: seen
            mock:
                - {'title': '\u0417\u0435\u0440\u043a\u0430\u043b\u0430 Mirrors 2008', 'url': 'mock://whatever'}
            if:
                - trakt_year > now.year - 1: reject
    """

    @pytest.mark.xfail(reason='VCR attempts to compare str to unicode')
    def test_unicode(self, execute_task):
        execute_task('test_unicode')
        with Session() as session:
            r = session.query(TraktMovieSearchResult).all()
            assert len(r) == 1, 'Should have added a search result'
            assert r[0].search == '\u0417\u0435\u0440\u043a\u0430\u043b\u0430 Mirrors 2008'.lower(), \
                'The search result should be lower case'
        execute_task('test_unicode')
        with Session() as session:
            r = session.query(TraktMovieSearchResult).all()
            assert len(r) == 1, 'Should not have added a new row'
