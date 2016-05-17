# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.manager import Session
from flexget.plugins.api_trakt import ApiTrakt, TraktActor, TraktMovieSearchResult, TraktShowSearchResult, TraktShow, \
    get_session
from future.utils import native

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
        assert entry['trakt_id'] == 1399, \
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
            assert series.id == entry['trakt_id'], 'trakt id should be the same as the first entry'
            assert series.title.lower() == entry['trakt_series_name'].lower(), 'series name should match first entry'

    def test_search_success(self, execute_task):
        task = execute_task('test_search_success')
        entry = task.find_entry('accepted', title='11-22-63.S01E01.HDTV.XViD-FlexGet')
        assert entry.get('trakt_id') == 102771, 'Should have returned the correct trakt id'

    def test_date(self, execute_task):
        task = execute_task('test_date')
        entry = task.find_entry(title='the daily show 2012-6-6')
        # Make sure show data got populated
        assert entry.get('trakt_id') == 2211, 'should have populated trakt show data'
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
        assert entry.get('trakt_id') == 46003, 'should have populated trakt show data'
        # We don't support lookup by absolute number at the moment, make sure there isn't a false positive
        if entry.get('trakt_id') == 916040:
            assert False, 'We support trakt episode lookup by absolute number now? Great! Change this test.'
        else:
            assert entry.get('trakt_episode_id') is None, 'false positive for episode match, we don\'t ' \
                                                          'support lookup by absolute number'

    def test_lookup_actors(self, execute_task):
        task = execute_task('test')
        actors = ['Hugh Laurie',
                  'Jesse Spencer',
                  'Jennifer Morrison',
                  'Omar Epps',
                  'Robert Sean Leonard',
                  'Peter Jacobson',
                  'Olivia Wilde',
                  'Odette Annable',
                  'Charlyne Yi',
                  'Anne Dudek',
                  'Kal Penn',
                  'Jennifer Crystal Foley',
                  'Bobbin Bergstrom']
        entry = task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        trakt_actors = list(entry['trakt_actors'].values())
        trakt_actors = [trakt_actor['name'] for trakt_actor in trakt_actors]
        assert entry['series_name'] == 'House', 'series lookup failed'
        assert set(trakt_actors) == set(actors), 'looking up actors for %s failed' % entry.get('title')
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
        translations = {
            u'el': {
                u'overview': u'\u0391\u03c0\u03cc \u03c4\u03b9\u03c2 \u03ba\u03cc\u03ba\u03ba\u03b9\u03bd\u03b5\u03c2 \u03b1\u03bc\u03bc\u03bf\u03c5\u03b4\u03b9\u03ad\u03c2 \u03c4\u03bf\u03c5 \u039d\u03cc\u03c4\u03bf\u03c5 \u03ba\u03b1\u03b9 \u03c4\u03b9\u03c2 \u03ac\u03b3\u03c1\u03b9\u03b5\u03c2 \u03c0\u03b5\u03b4\u03b9\u03ac\u03b4\u03b5\u03c2 \u03c4\u03b7\u03c2 \u0391\u03bd\u03b1\u03c4\u03bf\u03bb\u03ae\u03c2 \u03ad\u03c9\u03c2 \u03c4\u03bf\u03bd \u03c0\u03b1\u03b3\u03c9\u03bc\u03ad\u03bd\u03bf \u0392\u03bf\u03c1\u03c1\u03ac \u03ba\u03b1\u03b9 \u03c4\u03bf \u03b1\u03c1\u03c7\u03b1\u03af\u03bf \u03a4\u03b5\u03af\u03c7\u03bf\u03c2, \u03c0\u03bf\u03c5 \u03c0\u03c1\u03bf\u03c3\u03c4\u03b1\u03c4\u03b5\u03cd\u03b5\u03b9 \u03c4\u03bf \u03a3\u03c4\u03ad\u03bc\u03bc\u03b1 \u03b1\u03c0\u03cc \u03c3\u03ba\u03bf\u03c4\u03b5\u03b9\u03bd\u03ac \u03cc\u03bd\u03c4\u03b1, \u03bf\u03b9 \u03b9\u03c3\u03c7\u03c5\u03c1\u03ad\u03c2 \u03bf\u03b9\u03ba\u03bf\u03b3\u03ad\u03bd\u03b5\u03b9\u03b5\u03c2 \u03c4\u03c9\u03bd \u0395\u03c0\u03c4\u03ac \u0392\u03b1\u03c3\u03b9\u03bb\u03b5\u03af\u03c9\u03bd \u03b5\u03c0\u03b9\u03b4\u03af\u03b4\u03bf\u03bd\u03c4\u03b1\u03b9 \u03c3\u03b5 \u03bc\u03b9\u03b1 \u03b1\u03bd\u03b5\u03bb\u03ad\u03b7\u03c4\u03b7 \u03bc\u03ac\u03c7\u03b7 \u03c3\u03c4\u03b7 \u03b4\u03b9\u03b1\u03b4\u03bf\u03c7\u03ae \u03c4\u03bf\u03c5 \u03a3\u03b9\u03b4\u03b5\u03c1\u03ad\u03bd\u03b9\u03bf\u03c5 \u0398\u03c1\u03cc\u03bd\u03bf\u03c5. \u039c\u03b9\u03b1 \u03b9\u03c3\u03c4\u03bf\u03c1\u03af\u03b1 \u03b3\u03b5\u03bc\u03ac\u03c4\u03b7 \u03af\u03bd\u03c4\u03c1\u03b9\u03b3\u03ba\u03b5\u03c2 \u03ba\u03b1\u03b9 \u03c0\u03c1\u03bf\u03b4\u03bf\u03c3\u03af\u03b5\u03c2, \u03b9\u03c0\u03c0\u03bf\u03c4\u03b9\u03c3\u03bc\u03cc \u03ba\u03b1\u03b9 \u03c4\u03b9\u03bc\u03ae, \u03ba\u03b1\u03c4\u03b1\u03ba\u03c4\u03ae\u03c3\u03b5\u03b9\u03c2 \u03ba\u03b1\u03b9 \u03b8\u03c1\u03b9\u03ac\u03bc\u03b2\u03bf\u03c5\u03c2. \u03a3\u03c4\u03bf \u03a0\u03b1\u03b9\u03c7\u03bd\u03af\u03b4\u03b9 \u03c4\u03bf\u03c5 \u03a3\u03c4\u03ad\u03bc\u03bc\u03b1\u03c4\u03bf\u03c2, \u03b8\u03b1 \u03bd\u03b9\u03ba\u03ae\u03c3\u03b5\u03b9\u03c2 \u03ae \u03b8\u03b1 \u03c0\u03b5\u03b8\u03ac\u03bd\u03b5\u03b9\u03c2.',
                u'tagline': None, u'title': u'Game of Thrones'},
            u'en': {
                u'overview': u"Seven noble families fight for control of the mythical land of Westeros. Friction between the houses leads to full-scale war. All while a very ancient evil awakens in the farthest north. Amidst the war, a neglected military order of misfits, the Night's Watch, is all that stands between the realms of men and icy horrors beyond.",
                u'tagline': None, u'title': u'Game of Thrones'}, u'zh': {
                u'overview': u'\u6545\u4e8b\u80cc\u666f\u662f\u4e00\u4e2a\u865a\u6784\u7684\u4e16\u754c\uff0c\u4e3b\u8981\u5206\u4e3a\u4e24\u7247\u5927\u9646\uff0c\u4f4d\u4e8e\u897f\u9762\u7684\u662f\u201c\u65e5\u843d\u56fd\u5ea6\u201d\u7ef4\u65af\u7279\u6d1b\uff08Westeros\uff09\uff0c\u9762\u79ef\u7ea6\u7b49\u4e8e\u5357\u7f8e\u6d32\u3002\u4f4d\u4e8e\u4e1c\u9762\u7684\u662f\u4e00\u5757\u9762\u79ef\u3001\u5f62\u72b6\u8fd1\u4f3c\u4e8e\u4e9a\u6b27\u5927\u9646\u7684\u9646\u5730\u3002\u6545\u4e8b\u7684\u4e3b\u7ebf\u4fbf\u53d1\u751f\u5728\u7ef4\u65af\u7279\u6d1b\u5927\u9646\u4e0a\u3002\u4ece\u56fd\u738b\u52b3\u52c3\xb7\u62dc\u62c9\u5e2d\u6069\u524d\u5f80\u6b64\u5730\u62dc\u8bbf\u4ed6\u7684\u597d\u53cb\u4e34\u51ac\u57ce\u4e3b\u3001\u5317\u5883\u5b88\u62a4\u827e\u5fb7\xb7\u53f2\u5854\u514b\u5f00\u59cb\uff0c\u6e10\u6e10\u5c55\u793a\u4e86\u8fd9\u7247\u56fd\u5ea6\u7684\u5168\u8c8c\u3002\u5355\u7eaf\u7684\u56fd\u738b\uff0c\u803f\u76f4\u7684\u9996\u76f8\uff0c\u5404\u6000\u5fc3\u601d\u7684\u5927\u81e3\uff0c\u62e5\u5175\u81ea\u91cd\u7684\u56db\u65b9\u8bf8\u4faf\uff0c\u5168\u56fd\u4ec5\u9760\u7740\u4e00\u6839\u7ec6\u5f26\u7ef4\u7cfb\u7740\u8868\u9762\u7684\u548c\u5e73\uff0c\u800c\u5f53\u5f26\u65ad\u4e4b\u65f6\uff0c\u56fd\u5bb6\u518d\u5ea6\u9677\u5165\u65e0\u5c3d\u7684\u6218\u4e71\u4e4b\u4e2d\u3002\u800c\u66f4\u8ba9\u4eba\u60ca\u609a\u7684\u3001\u90a3\u4e9b\u8fdc\u53e4\u7684\u4f20\u8bf4\u548c\u65e9\u5df2\u706d\u7edd\u7684\u751f\u7269\uff0c\u6b63\u91cd\u65b0\u56de\u5230\u8fd9\u7247\u571f\u5730\u3002',
                u'tagline': None, u'title': u'\u6743\u529b\u7684\u6e38\u620f'},
            u'vi': {u'overview': u'', u'tagline': None, u'title': u'Game of Thrones'},
            u'is': {u'overview': u'', u'tagline': None, u'title': u'Kr\xfanuleikar'}, u'it': {
                u'overview': u'Il Trono di Spade (Game of Thrones) \xe8 una serie televisiva statunitense di genere fantasy creata da David Benioff e D.B. Weiss, che ha debuttato il 17 aprile 2011 sul canale via cavo HBO. \xc8 nata come trasposizione televisiva del ciclo di romanzi Cronache del ghiaccio e del fuoco (A Song of Ice and Fire) di George R. R. Martin.\n\nLa serie racconta le avventure di molti personaggi che vivono in un grande mondo immaginario costituito principalmente da due continenti. Il centro pi\xf9 grande e civilizzato del continente occidentale \xe8 la citt\xe0 capitale Approdo del Re, dove risiede il Trono di Spade. La lotta per la conquista del trono porta le pi\xf9 grandi famiglie del continente a scontrarsi o allearsi tra loro in un contorto gioco del potere. Ma oltre agli uomini, emergono anche altre forze oscure e magiche.',
                u'tagline': None, u'title': u'Il Trono di Spade'},
            u'lb': {u'overview': u'', u'tagline': None, u'title': u'Game of Thrones'},
            u'ar': {u'overview': u'', u'tagline': None, u'title': u'Game of Thrones'}, u'cs': {
                u'overview': u'Kontinent, kde l\xe9ta trvaj\xed des\xedtky rok\u016f a zimy se mohou prot\xe1hnout na cel\xfd lidsk\xfd \u017eivot, za\u010d\xednaj\xed su\u017eovat nepokoje. V\u0161ech Sedm kr\xe1lovstv\xed Z\xe1padozem\xed \u2013 pletich\xe1\u0159sk\xfd jih, divok\xe9 v\xfdchodn\xed krajiny i ledov\xfd sever ohrani\u010den\xfd starobylou Zd\xed, kter\xe1 chr\xe1n\xed kr\xe1lovstv\xed p\u0159ed pronik\xe1n\xedm temnoty \u2013 je zm\xedt\xe1no bojem dvou mocn\xfdch rod\u016f na \u017eivot a na smrt o nadvl\xe1du nad celou \u0159\xed\u0161\xed. Zem\xed ot\u0159\xe1s\xe1 zrada, cht\xed\u010d, intriky a nadp\u0159irozen\xe9 s\xedly. Krvav\xfd boj o \u017delezn\xfd tr\u016fn, post nejvy\u0161\u0161\xedho vl\xe1dce Sedmi kr\xe1lovstv\xed, bude m\xedt nep\u0159edv\xeddateln\xe9 a dalekos\xe1hl\xe9 d\u016fsledky\u2026',
                u'tagline': None, u'title': u'Hra o tr\u016fny'},
            u'id': {u'overview': u'', u'tagline': None, u'title': u'Game of Thrones'}, u'es': {
                u'overview': u'Juego de Tronos es una serie de televisi\xf3n de drama y fantas\xeda creada para la HBO por David Benioff y D. B. Weiss. Es una adaptaci\xf3n de la saga de novelas de fantas\xeda Canci\xf3n de Hielo y Fuego de George R. R. Martin. La primera de las novelas es la que da nombre a la serie.\n\nLa serie, ambientada en los continentes ficticios de Westeros y Essos al final de un verano de una decada de duraci\xf3n, entrelaza varias l\xedneas argumentales. La primera sigue a los miembros de varias casas nobles inmersos en una guerra civil por conseguir el Trono de Hierro de los Siete Reinos. La segunda trata sobre la creciente amenaza de un inminente invierno y sobre las temibles criaturas del norte. La tercera relata los esfuerzos por reclamar el trono de los \xfaltimos miembros exiliados de una dinast\xeda destronada. A pesar de sus personajes moralmente ambiguos, la serie profundiza en los problemas de la jerarqu\xeda social, religi\xf3n, lealtad, corrupci\xf3n, sexo, guerra civil, crimen y castigo.',
                u'tagline': None, u'title': u'Juego de Tronos'}, u'ru': {
                u'overview': u'\u041a \u043a\u043e\u043d\u0446\u0443 \u043f\u043e\u0434\u0445\u043e\u0434\u0438\u0442 \u0432\u0440\u0435\u043c\u044f \u0431\u043b\u0430\u0433\u043e\u0434\u0435\u043d\u0441\u0442\u0432\u0438\u044f, \u0438 \u043b\u0435\u0442\u043e, \u0434\u043b\u0438\u0432\u0448\u0435\u0435\u0441\u044f \u043f\u043e\u0447\u0442\u0438 \u0434\u0435\u0441\u044f\u0442\u0438\u043b\u0435\u0442\u0438\u0435, \u0443\u0433\u0430\u0441\u0430\u0435\u0442. \u0412\u043e\u043a\u0440\u0443\u0433 \u0441\u0440\u0435\u0434\u043e\u0442\u043e\u0447\u0438\u044f \u0432\u043b\u0430\u0441\u0442\u0438 \u0421\u0435\u043c\u0438 \u043a\u043e\u0440\u043e\u043b\u0435\u0432\u0441\u0442\u0432, \u0416\u0435\u043b\u0435\u0437\u043d\u043e\u0433\u043e \u0442\u0440\u043e\u043d\u0430, \u0437\u0440\u0435\u0435\u0442 \u0437\u0430\u0433\u043e\u0432\u043e\u0440, \u0438 \u0432 \u044d\u0442\u043e \u043d\u0435\u043f\u0440\u043e\u0441\u0442\u043e\u0435 \u0432\u0440\u0435\u043c\u044f \u043a\u043e\u0440\u043e\u043b\u044c \u0440\u0435\u0448\u0430\u0435\u0442 \u0438\u0441\u043a\u0430\u0442\u044c \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0438 \u0443 \u0434\u0440\u0443\u0433\u0430 \u044e\u043d\u043e\u0441\u0442\u0438 \u042d\u0434\u0434\u0430\u0440\u0434\u0430 \u0421\u0442\u0430\u0440\u043a\u0430. \u0412 \u043c\u0438\u0440\u0435, \u0433\u0434\u0435 \u0432\u0441\u0435 \u2014 \u043e\u0442 \u043a\u043e\u0440\u043e\u043b\u044f \u0434\u043e \u043d\u0430\u0435\u043c\u043d\u0438\u043a\u0430 \u2014 \u0440\u0432\u0443\u0442\u0441\u044f \u043a \u0432\u043b\u0430\u0441\u0442\u0438, \u043f\u043b\u0435\u0442\u0443\u0442 \u0438\u043d\u0442\u0440\u0438\u0433\u0438 \u0438 \u0433\u043e\u0442\u043e\u0432\u044b \u0432\u043e\u043d\u0437\u0438\u0442\u044c \u043d\u043e\u0436 \u0432 \u0441\u043f\u0438\u043d\u0443, \u0435\u0441\u0442\u044c \u043c\u0435\u0441\u0442\u043e \u0438 \u0431\u043b\u0430\u0433\u043e\u0440\u043e\u0434\u0441\u0442\u0432\u0443, \u0441\u043e\u0441\u0442\u0440\u0430\u0434\u0430\u043d\u0438\u044e \u0438 \u043b\u044e\u0431\u0432\u0438. \u041c\u0435\u0436\u0434\u0443 \u0442\u0435\u043c, \u043d\u0438\u043a\u0442\u043e \u043d\u0435 \u0437\u0430\u043c\u0435\u0447\u0430\u0435\u0442 \u043f\u0440\u043e\u0431\u0443\u0436\u0434\u0435\u043d\u0438\u0435 \u0442\u044c\u043c\u044b \u0438\u0437 \u043b\u0435\u0433\u0435\u043d\u0434 \u0434\u0430\u043b\u0435\u043a\u043e \u043d\u0430 \u0421\u0435\u0432\u0435\u0440\u0435 \u2014 \u0438 \u043b\u0438\u0448\u044c \u0421\u0442\u0435\u043d\u0430 \u0437\u0430\u0449\u0438\u0449\u0430\u0435\u0442 \u0436\u0438\u0432\u044b\u0445 \u043a \u044e\u0433\u0443 \u043e\u0442 \u043d\u0435\u0435.',
                u'tagline': None,
                u'title': u'\u0418\u0433\u0440\u0430 \u043f\u0440\u0435\u0441\u0442\u043e\u043b\u043e\u0432'}, u'nl': {
                u'overview': u'Een eeuwenoude machtsstrijd barst los in het land waar de zomers decennia duren en de winters een leven lang kunnen aanslepen. Twee machtige geslachten - de regerende Baratheons en de verbannen Targaryens - maken zich op om de IJzeren Troon te claimen en de Zeven Koninkrijken van Westeros onder hun controle te krijgen. Maar in een tijdperk waarin verraad, lust, intriges en bovennatuurlijke krachten hoogtij vieren, zal hun dodelijke kat-en-muisspelletje onvoorziene en verreikende gevolgen hebben. Achter een eeuwenoude, gigantische muur van ijs in het uiterste noorden van Westeros maakt een kille vijand zich immers op om het land onder de voet te lopen. Gebaseerd op de bestseller fantasyreeks "A Song of Ice and Fire" van George R.R. Martin.',
                u'tagline': None, u'title': u'Game of Thrones'}, u'pt': {
                u'overview': u'Adaptada por David Benioff e Dan Weiss, a primeira temporada, com dez epis\xf3dios encomendados, ter\xe1 como base o livro \u201cGame of Thrones\u201d. Game of Thrones se passa em Westeros, uma terra reminiscente da Europa Medieval, onde as esta\xe7\xf5es duram por anos ou at\xe9 mesmo d\xe9cadas. A hist\xf3ria gira em torno de uma batalha entre os Sete Reinos, onde duas fam\xedlias dominantes est\xe3o lutando pelo controle do Trono de Ferro, cuja posse assegura a sobreviv\xeancia durante o inverno de 40 anos que est\xe1 por vir. A s\xe9rie \xe9 encabe\xe7ada por Lena Headey, Sean Bean e Mark Addy. Bean interpreta Eddard \u201cNed\u201d Stark, Lorde de Winterfell, um homem conhecido pelo seu senso de honra e justi\xe7a que se torna o principal conselheiro do Rei Robert, vivido por Addy.',
                u'tagline': None, u'title': u'A Guerra dos Tronos'}, u'tw': {u'overview': u'', u'tagline': None,
                                                                             u'title': u'\u51b0\u8207\u706b\u4e4b\u6b4c\uff1a\u6b0a\u529b\u904a\u6232'},
            u'tr': {
                u'overview': u"Krall\u0131k dedi\u011fin sava\u015fs\u0131z olur mu? En g\xfc\xe7l\xfc krall\u0131\u011f\u0131 kurup, huzuru sa\u011flam\u0131\u015f olsan bile bu g\xfcc\xfc elinde nas\u0131l koruyacaks\u0131n? Burada yanl\u0131\u015f yapana yer yok, affetmek yok. Kuzey Krall\u0131\u011f\u0131n\u0131n h\xfck\xfcmdar\u0131 Lord Ned Stark, uzun ve zorlu sava\u015flardan sonra anayurduna d\xf6n\xfcp krall\u0131\u011f\u0131n\u0131 b\xfct\xfcnl\xfck i\xe7erisinde tutmay\u0131 ba\u015farm\u0131\u015ft\u0131r. Kral Robert Baratheon ile y\u0131llarca omuz omuza \xe7arp\u0131\u015fan ve Baratheon'un kral olmas\u0131n\u0131 sa\u011flayan Ned Stark'\u0131n tek istedi\u011fi kuzey s\u0131n\u0131rlar\u0131n\u0131 koruyan krall\u0131\u011f\u0131nda ailesiyle ve halk\u0131yla ya\u015famakt\u0131r. \n\nFakat suyun \xf6te yan\u0131nda kendi topraklar\u0131ndan ve krall\u0131\u011f\u0131ndan kovuldu\u011funu iddia eden Viserys Targaryen , k\u0131z karde\u015fi Daenerys'i barbar kavimlerin ba\u015f\u0131 Han Drogo'ya vererek, g\xfc\xe7 birli\u011fi planlar\u0131 yapmaktad\u0131r. Taht\u0131n\u0131 b\xfcy\xfck bir i\u015ftahla geri isteyen ama kraliyet oyunlar\u0131ndan habersiz olan Viserys'in planlar\u0131 Kral Baratheon'a ula\u015f\u0131r. Sava\u015f alan\u0131nda b\xfcy\xfck cengaver olan ama \xfclke ve aile y\xf6netiminde ayn\u0131 ba\u015far\u0131y\u0131 tutturamayan Baratheon'un tamamen g\xfcvenebilece\u011fi ve her yanl\u0131\u015f hamlesini arkas\u0131ndan toplayacak yeni bir sa\u011f kola ihtiyac\u0131 vard\u0131r. Kuzeyin Lordu Ned Stark bu g\xf6rev i\xe7in se\xe7ilen tek aday isimdir. K\u0131\u015f yakla\u015f\u0131yor...\n\nHanedan entrikalar\u0131, kap\u0131l\u0131 kap\u0131lar ard\u0131nda d\xf6nen oyunlar, birilerinin kuyusunu kazmak i\xe7in d\xfc\u015fman\u0131n koynuna girmekten \xe7ekinmeyen kad\u0131nlar, karde\u015fler aras\u0131 \xe7eki\u015fmeler, d\u0131\u015flanmalar... Hepsi tek bir hedef i\xe7in: taht kavgas\u0131..",
                u'tagline': None, u'title': u'Taht Oyunlar\u0131'},
            u'lt': {u'overview': u'', u'tagline': None, u'title': u'Sost\u0173 karai'},
            u'th': {u'overview': u'', u'tagline': None,
                    u'title': u'\u0e40\u0e01\u0e21\u0e25\u0e48\u0e32\u0e1a\u0e31\u0e25\u0e25\u0e31\u0e07\u0e01\u0e4c'},
            u'ro': {u'overview': u'', u'tagline': None, u'title': u'Urzeala tronurilor'}, u'pl': {
                u'overview': u'Siedem rodzin szlacheckich walczy o panowanie nad ziemiami krainy Westeros. Polityczne i seksualne intrygi s\u0105 na porz\u0105dku dziennym. Pierwszorz\u0119dne role wiod\u0105 rodziny: Stark, Lannister i Baratheon. Robert Baratheon, kr\xf3l Westeros, prosi swojego starego przyjaciela, Eddarda Starka, aby s\u0142u\u017cy\u0142 jako jego g\u0142\xf3wny doradca. Eddard, podejrzewaj\u0105c, \u017ce jego poprzednik na tym stanowisku zosta\u0142 zamordowany, przyjmuje propozycj\u0119, aby dog\u0142\u0119bnie zbada\u0107 spraw\u0119. Okazuje si\u0119, \u017ce przej\u0119cie tronu planuje kilka rodzin. Lannisterowie, familia kr\xf3lowej, staje si\u0119 podejrzana o podst\u0119pne knucie spisku. Po drugiej stronie morza, pozbawieni w\u0142adzy ostatni przedstawiciele poprzednio rz\u0105dz\u0105cego rodu, Targaryen\xf3w, r\xf3wnie\u017c planuj\u0105 odzyska\u0107 kontrol\u0119 nad kr\xf3lestwem. Narastaj\u0105cy konflikt pomi\u0119dzy rodzinami, do kt\xf3rego w\u0142\u0105czaj\u0105 si\u0119 r\xf3wnie\u017c inne rody, prowadzi do wojny. W mi\u0119dzyczasie na dalekiej p\xf3\u0142nocy budzi si\u0119 starodawne z\u0142o. W chaosie pe\u0142nym walk i konflikt\xf3w tylko grupa wyrzutk\xf3w zwana Nocn\u0105 Stra\u017c\u0105 stoi pomi\u0119dzy kr\xf3lestwem ludzi, a horrorem kryj\u0105cym si\u0119 poza nim.',
                u'tagline': None, u'title': u'Gra o Tron'}, u'fr': {
                u'overview': u"Il y a tr\xe8s longtemps, \xe0 une \xe9poque oubli\xe9e, une force a d\xe9truit l'\xe9quilibre des saisons. Dans un pays o\xf9 l'\xe9t\xe9 peut durer plusieurs ann\xe9es et l'hiver toute une vie, des forces sinistres et surnaturelles se pressent aux portes du Royaume des Sept Couronnes. La confr\xe9rie de la Garde de Nuit, prot\xe9geant le Royaume de toute cr\xe9ature pouvant provenir d'au-del\xe0 du Mur protecteur, n'a plus les ressources n\xe9cessaires pour assurer la s\xe9curit\xe9 de tous. Apr\xe8s un \xe9t\xe9 de dix ann\xe9es, un hiver rigoureux s'abat sur le Royaume avec la promesse d'un avenir des plus sombres. Pendant ce temps, complots et rivalit\xe9s se jouent sur le continent pour s'emparer du Tr\xf4ne de fer, le symbole du pouvoir absolu.",
                u'tagline': None, u'title': u'Le Tr\xf4ne de fer'}, u'bg': {
                u'overview': u'\u201e\u0418\u0433\u0440\u0430 \u043d\u0430 \u0442\u0440\u043e\u043d\u043e\u0432\u0435\u201c \u0435 \u0441\u0435\u0440\u0438\u0430\u043b \u043d\u0430 HBO, \u043a\u043e\u0439\u0442\u043e \u0441\u043b\u0435\u0434\u0432\u0430 \u0438\u0441\u0442\u043e\u0440\u0438\u044f\u0442\u0430 \u043d\u0430 \u0444\u0435\u043d\u0442\u044a\u0437\u0438 \u0435\u043f\u043e\u0441 \u043f\u043e\u0440\u0435\u0434\u0438\u0446\u0430\u0442\u0430 \u201e\u041f\u0435\u0441\u0435\u043d \u0437\u0430 \u043e\u0433\u044a\u043d \u0438 \u043b\u0435\u0434\u201c, \u0432\u0437\u0435\u043c\u0430\u0439\u043a\u0438 \u0438\u043c\u0435\u0442\u043e \u043d\u0430 \u043f\u044a\u0440\u0432\u0430\u0442\u0430 \u043a\u043d\u0438\u0433\u0430. \u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435\u0442\u043e \u043d\u0430 \u0441\u0435\u0440\u0438\u0430\u043b\u0430 \u0441\u0435 \u0440\u0430\u0437\u0432\u0438\u0432\u0430 \u0432 \u0421\u0435\u0434\u0435\u043c\u0442\u0435 \u043a\u0440\u0430\u043b\u0441\u0442\u0432\u0430 \u043d\u0430 \u0412\u0435\u0441\u0442\u0435\u0440\u043e\u0441, \u043a\u044a\u0434\u0435\u0442\u043e \u043b\u044f\u0442\u043e\u0442\u043e \u043f\u0440\u043e\u0434\u044a\u043b\u0436\u0430\u0432\u0430 \u0434\u0435\u0441\u0435\u0442\u0438\u043b\u0435\u0442\u0438\u044f, \u0430 \u0437\u0438\u043c\u0430\u0442\u0430 \u2013 \u0446\u044f\u043b\u0430 \u0432\u0435\u0447\u043d\u043e\u0441\u0442.',
                u'tagline': None,
                u'title': u'\u0418\u0433\u0440\u0430 \u043d\u0430 \u0442\u0440\u043e\u043d\u043e\u0432\u0435'}, u'hr': {
                u'overview': u'Game of Thrones (Igra Prijestolja) srednjovjekovna je fantazija bazirana na seriji romana Georgea R. R. Martina smje\u0161tena u izmi\u0161ljenom svijetu Sedam kraljevina i prati dinasti\u010dka previranja i borbu nekoliko Ku\u0107a za kontrolu nad \u017deljeznim prijestoljem. Osim me\u0111usobnih borbi plemi\u0107kih obitelji, stanovni\u0161tvu prijeti natprirodna invazija s ledenog sjevera, prognana zmajeva princeza koja \u017eeli povratiti obiteljsko naslije\u0111e te zima koja \u0107e trajati godinama.\n\nNakon sumnjive smrti namjesnika kralja Roberta Baratheona, on sa svojom kraljicom Cersei iz bogate i iskvarene obitelji Lannister kre\u0107e na putovanje na sjever svome prijatelju knezu Eddardu Starku od O\u0161trozimlja, od kojega zatra\u017ei za postane novi Kraljev Namjesnik. Eddard nevoljko pristaje i tu zapo\u010dinje epska pri\u010da o \u010dasti i izdaji, ljubavi i mr\u017enji, tajnama i osveti...',
                u'tagline': None, u'title': u'Igra Prijestolja'}, u'de': {
                u'overview': u'Die Handlung ist in einer fiktiven Welt angesiedelt und spielt auf den Kontinenten Westeros (den Sieben K\xf6nigreichen sowie im Gebiet der \u201eMauer\u201c und jenseits davon im Norden) und Essos. In dieser Welt ist die L\xe4nge der Sommer und Winter unvorhersehbar und variabel; eine Jahreszeit kann Jahre oder sogar Jahrzehnte dauern. Der Handlungsort auf dem Kontinent Westeros in den Sieben K\xf6nigreichen \xe4hnelt dabei stark dem mittelalterlichen Europa. Die Geschichte spielt am Ende eines langen Sommers und wird in drei Handlungsstr\xe4ngen weitgehend parallel erz\xe4hlt. In den Sieben K\xf6nigreichen bauen sich zwischen den m\xe4chtigsten Adelsh\xe4usern des Reiches Spannungen auf, die schlie\xdflich zum offenen Thronkampf f\xfchren. Gleichzeitig droht der Wintereinbruch und es zeichnet sich eine Gefahr durch eine fremde Rasse im hohen Norden von Westeros ab. Der dritte Handlungsstrang spielt auf dem Kontinent Essos, wo Daenerys Targaryen, Mitglied der vor Jahren abgesetzten K\xf6nigsfamilie, bestrebt ist, wieder an die Macht zu gelangen. Die komplexe Handlung umfasst zahlreiche Figuren und thematisiert unter anderem Politik und Machtk\xe4mpfe, Gesellschaftsverh\xe4ltnisse und Religion.',
                u'tagline': None, u'title': u'Game of Thrones'}, u'da': {
                u'overview': u'George R. R. Martins Game of Thrones er en lang fort\xe6lling gennem syv b\xf8ger. Handlingen foreg\xe5r i et fiktivt kongerige kaldet Westeros. Denne middelalderlige verden er fuld af k\xe6mper, profetier og fortryllede skove, og bag en mur af is, der adskiller Riget, truer sp\xf8gelser og andre farer. Men de overnaturlige elementer er ikke rigtig s\xe5 fremtr\xe6dende i serien. Den narrative ramme er den hensynsl\xf8se kamp om magten, hvilket involverer en r\xe6kke konger, riddere og herrem\xe6nd med navne som Baratheon, Stark og Lannister. Det er ingen opl\xf8ftende historie, hvor det gode n\xf8dvendigvis sejrer frem for det onde, eller hvor det egentlig er s\xe5 let at afg\xf8re, hvad der er godt og ondt. Men Martin form\xe5r at tryllebinde publikum - ogs\xe5 dem, der normalt ikke synes om magi og fantasiverdener.',
                u'tagline': None, u'title': u'Game of Thrones'}, u'fa': {
                u'overview': u'\u0647\u0641\u062a \u062e\u0627\u0646\u062f\u0627\u0646 \u0627\u0634\u0631\u0627\u0641\u06cc \u0628\u0631\u0627\u06cc \u062d\u0627\u06a9\u0645\u06cc\u062a \u0628\u0631 \u0633\u0631\u0632\u0645\u06cc\u0646 \u0627\u0641\u0633\u0627\u0646\u0647 \u0627\u06cc \xab\u0648\u0633\u062a\u0631\u0648\u0633\xbb \u062f\u0631 \u062d\u0627\u0644 \u0633\u062a\u06cc\u0632 \u0628\u0627 \u06cc\u06a9\u062f\u06cc\u06af\u0631\u0646\u062f. \u062e\u0627\u0646\u062f\u0627\u0646 \xab\u0627\u0633\u062a\u0627\u0631\u06a9\xbb\u060c \xab\u0644\u0646\u06cc\u0633\u062a\u0631\xbb \u0648 \xab\u0628\u0627\u0631\u0627\u062b\u06cc\u0648\u0646\xbb \u0628\u0631\u062c\u0633\u062a\u0647 \u062a\u0631\u06cc\u0646 \u0622\u0646\u0647\u0627 \u0647\u0633\u062a\u0646\u062f. \u062f\u0627\u0633\u062a\u0627\u0646 \u0627\u0632 \u062c\u0627\u06cc\u06cc \u0634\u0631\u0648\u0639 \u0645\u06cc \u0634\u0648\u062f \u06a9\u0647 \xab\u0631\u0627\u0628\u0631\u062a \u0628\u0627\u0631\u0627\u062b\u06cc\u0648\u0646\xbb \u067e\u0627\u062f\u0634\u0627\u0647 \u0648\u0633\u062a\u0631\u0648\u0633\u060c \u0627\u0632 \u062f\u0648\u0633\u062a \u0642\u062f\u06cc\u0645\u06cc \u0627\u0634\u060c \xab\u0627\u062f\u0627\u0631\u062f\xbb \u0627\u0631\u0628\u0627\u0628 \u062e\u0627\u0646\u062f\u0627\u0646 \u0627\u0633\u062a\u0627\u0631\u06a9\u060c \u062a\u0642\u0627\u0636\u0627 \u0645\u06cc \u06a9\u0646\u062f \u06a9\u0647 \u0628\u0639\u0646\u0648\u0627\u0646 \u0645\u0634\u0627\u0648\u0631 \u067e\u0627\u062f\u0634\u0627\u0647\u060c \u0628\u0631\u062a\u0631\u06cc\u0646 \u0633\u0645\u062a \u062f\u0631\u0628\u0627\u0631\u060c \u0628\u0647 \u0627\u0648 \u062e\u062f\u0645\u062a \u06a9\u0646\u062f. \u0627\u06cc\u0646 \u062f\u0631 \u062d\u0627\u0644\u06cc \u0627\u0633\u062a \u06a9\u0647 \u0645\u0634\u0627\u0648\u0631 \u0642\u0628\u0644\u06cc \u0628\u0647 \u0637\u0631\u0632 \u0645\u0631\u0645\u0648\u0632\u06cc \u0628\u0647 \u0642\u062a\u0644 \u0631\u0633\u06cc\u062f\u0647 \u0627\u0633\u062a\u060c \u0628\u0627 \u0627\u06cc\u0646 \u062d\u0627\u0644 \u0627\u062f\u0627\u0631\u062f \u062a\u0642\u0627\u0636\u0627\u06cc \u067e\u0627\u062f\u0634\u0627\u0647 \u0631\u0627 \u0645\u06cc \u067e\u0630\u06cc\u0631\u062f \u0648 \u0628\u0647 \u0633\u0631\u0632\u0645\u06cc\u0646 \u0634\u0627\u0647\u06cc \u0631\u0627\u0647\u06cc \u0645\u06cc \u0634\u0648\u062f. \u062e\u0627\u0646\u0648\u0627\u062f\u0647 \u0645\u0644\u06a9\u0647\u060c \u06cc\u0639\u0646\u06cc \u0644\u0646\u06cc\u0633\u062a\u0631 \u0647\u0627 \u062f\u0631 \u062d\u0627\u0644 \u062a\u0648\u0637\u0626\u0647 \u0628\u0631\u0627\u06cc \u0628\u062f\u0633\u062a \u0622\u0648\u0631\u062f\u0646 \u0642\u062f\u0631\u062a \u0647\u0633\u062a\u0646\u062f. \u0627\u0632 \u0633\u0648\u06cc \u062f\u06cc\u06af\u0631\u060c \u0628\u0627\u0632\u0645\u0627\u0646\u062f\u0647 \u0647\u0627\u06cc \u062e\u0627\u0646\u062f\u0627\u0646 \u067e\u0627\u062f\u0634\u0627\u0647 \u0642\u0628\u0644\u06cc \u0648\u0633\u062a\u0631\u0648\u0633\u060c \xab\u062a\u0627\u0631\u06af\u0631\u06cc\u0646 \u0647\u0627\xbb \u0646\u06cc\u0632 \u0646\u0642\u0634\u0647 \u06cc \u067e\u0633 \u06af\u0631\u0641\u062a\u0646 \u062a\u0627\u062c \u0648 \u062a\u062e\u062a \u0631\u0627 \u062f\u0631 \u0633\u0631 \u0645\u06cc \u067e\u0631\u0648\u0631\u0627\u0646\u0646\u062f\u060c \u0648 \u062a\u0645\u0627\u0645 \u0627\u06cc\u0646 \u0645\u0627\u062c\u0631\u0627\u0647\u0627 \u0645\u0648\u062c\u0628 \u062f\u0631 \u06af\u0631\u0641\u062a\u0646 \u0646\u0628\u0631\u062f\u06cc \u0639\u0638\u06cc\u0645 \u0645\u06cc\u0627\u0646 \u0622\u0646\u200c\u0647\u0627 \u062e\u0648\u0627\u0647\u062f \u0634\u062f...',
                u'tagline': None, u'title': u'\u0628\u0627\u0632\u06cc \u062a\u0627\u062c \u0648 \u062a\u062e\u062a'},
            u'bs': {
                u'overview': u'Game of Thrones (Igra Prijestolja) srednjovjekovna je fantazija bazirana na seriji romana Georgea R. R. Martina smje\u0161tena u izmi\u0161ljenom svijetu Sedam kraljevina i prati dinasti\u010dka previranja i borbu nekoliko Ku\u0107a za kontrolu nad \u017deljeznim prijestoljem. Osim me\u0111usobnih borbi plemi\u0107kih obitelji, stanovni\u0161tvu prijeti natprirodna invazija s ledenog sjevera, prognana zmajeva princeza koja \u017eeli povratiti obiteljsko naslije\u0111e te zima koja \u0107e trajati godinama.\n\nNakon sumnjive smrti namjesnika kralja Roberta Baratheona, on sa svojom kraljicom Cersei iz bogate i iskvarene obitelji Lannister kre\u0107e na putovanje na sjever svome prijatelju knezu Eddardu Starku od O\u0161trozimlja, od kojega zatra\u017ei za postane novi Kraljev Namjesnik. Eddard nevoljko pristaje i tu zapo\u010dinje epska pri\u010da o \u010dasti i izdaji, ljubavi i mr\u017enji, tajnama i osveti...',
                u'tagline': None, u'title': u'Game of Thrones'}, u'fi': {
                u'overview': u'George R.R. Martinin kirjoihin perustuva, eeppinen sarja valtataistelusta, kunniasta ja petoksesta myyttisess\xe4 Westerosissa',
                u'tagline': None, u'title': u'Game of Thrones'}, u'hu': {
                u'overview': u'Westeros f\xf6l\xf6tt valaha a s\xe1rk\xe1nykir\xe1lyok uralkodtak, \xe1m a Targaryen-dinaszti\xe1t 15 \xe9vvel ezel\u0151tt el\u0171zt\xe9k, \xe9s most Robert Baratheon uralkodik h\u0171 bar\xe1tai, Jon Arryn, majd Eddard Stark seg\xedts\xe9g\xe9vel. A konfliktus k\xf6z\xe9ppontj\xe1ban Deres urai, a Starkok \xe1llnak. Olyanok, mint a f\xf6ld, ahol sz\xfclettek: makacs, kem\xe9ny jellem\u0171 csal\xe1d. Szem\xfcnk el\u0151tt h\u0151s\xf6k, gazemberek \xe9s egy gonosz hatalom t\xf6rt\xe9nete elevenedik meg. \xc1m hamar r\xe1 kell \xe9bredn\xfcnk, hogy ebben a vil\xe1gban m\xe9gsem egyszer\u0171en j\xf3k \xe9s gonoszok ker\xfclnek szembe egym\xe1ssal, hanem mesterien \xe1br\xe1zolt jellemek bontakoznak ki el\u0151tt\xfcnk k\xfcl\xf6nb\xf6z\u0151 v\xe1gyakkal, c\xe9lokkal, f\xe9lelmekkel \xe9s sebekkel. George R.R. Martin nagy siker\u0171, A t\u0171z \xe9s j\xe9g dala c\xedm\u0171 reg\xe9nyciklus\xe1nak els\u0151 k\xf6tete sorozat form\xe1j\xe1ban, amelyben k\xe9t nagyhatalm\xfa csal\xe1d v\xedv hal\xe1los harcot a Westeros H\xe9t Kir\xe1lys\xe1g\xe1nak ir\xe1ny\xedt.',
                u'tagline': None, u'title': u'Tr\xf3nok harca'}, u'he': {
                u'overview': u'\u05de\u05e9\u05d7\u05e7\u05d9 \u05d4\u05db\u05e1 \u05e9\u05dc \u05d0\u05d9\u05d9\u05e5\'-\u05d1\u05d9-\u05d0\u05d5 \u05d4\u05d9\u05d0 \u05e2\u05d9\u05d1\u05d5\u05d3 \u05dc\u05d8\u05dc\u05d5\u05d5\u05d9\u05d6\u05d9\u05d4 \u05e9\u05dc \u05e1\u05d3\u05e8\u05ea \u05d4\u05e1\u05e4\u05e8\u05d9\u05dd \u05e8\u05d1\u05d9-\u05d4\u05de\u05db\u05e8 \u05e9\u05dc \u05d2\'\u05d5\u05e8\u05d2\' \u05e8.\u05e8. \u05de\u05e8\u05d8\u05d9\u05df ("\u05e9\u05d9\u05e8 \u05e9\u05dc \u05d0\u05e9 \u05d5\u05e9\u05dc \u05e7\u05e8\u05d7") \u05d1\u05d4\u05dd \u05d4\u05e7\u05d9\u05e5 \u05e0\u05de\u05e9\u05da \u05e2\u05dc \u05e4\u05e0\u05d9 \u05e2\u05e9\u05d5\u05e8\u05d9\u05dd, \u05d4\u05d7\u05d5\u05e8\u05e3 \u05d9\u05db\u05d5\u05dc \u05dc\u05d4\u05d9\u05de\u05e9\u05da \u05d3\u05d5\u05e8 \u05d5\u05d4\u05de\u05d0\u05d1\u05e7 \u05e2\u05dc \u05db\u05e1 \u05d4\u05d1\u05e8\u05d6\u05dc \u05d4\u05d7\u05dc. \u05d4\u05d5\u05d0 \u05d9\u05e9\u05ea\u05e8\u05e2 \u05de\u05df \u05d4\u05d3\u05e8\u05d5\u05dd, \u05d1\u05d5 \u05d4\u05d7\u05d5\u05dd \u05de\u05d5\u05dc\u05d9\u05d3 \u05de\u05d6\u05d9\u05de\u05d5\u05ea, \u05ea\u05d0\u05d5\u05d5\u05ea \u05d5\u05e7\u05e0\u05d5\u05e0\u05d9\u05d5\u05ea; \u05d0\u05dc \u05d0\u05d3\u05de\u05d5\u05ea \u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05e0\u05e8\u05d7\u05d1\u05d5\u05ea \u05d5\u05d4\u05e4\u05e8\u05d0\u05d9\u05d5\u05ea; \u05db\u05dc \u05d4\u05d3\u05e8\u05da \u05d0\u05dc \u05d4\u05e6\u05e4\u05d5\u05df \u05d4\u05e7\u05e4\u05d5\u05d0, \u05e9\u05dd \u05d7\u05d5\u05de\u05ea \u05e7\u05e8\u05d7 \u05d0\u05d3\u05d9\u05e8\u05d4 \u05de\u05d2\u05e0\u05d4 \u05e2\u05dc \u05d4\u05de\u05de\u05dc\u05db\u05d4 \u05de\u05e4\u05e0\u05d9 \u05db\u05d5\u05d7\u05d5\u05ea \u05d4\u05d0\u05d5\u05e4\u05dc \u05d4\u05e9\u05d5\u05db\u05e0\u05d9\u05dd \u05de\u05e6\u05d3\u05d4 \u05d4\u05e9\u05e0\u05d9. \u05de\u05dc\u05db\u05d9\u05dd \u05d5\u05de\u05dc\u05db\u05d5\u05ea, \u05d0\u05d1\u05d9\u05e8\u05d9\u05dd \u05d5\u05e4\u05d5\u05e8\u05e2\u05d9 \u05d7\u05d5\u05e7, \u05e9\u05e7\u05e8\u05e0\u05d9\u05dd, \u05d0\u05d3\u05d5\u05e0\u05d9\u05dd \u05d5\u05d0\u05e0\u05e9\u05d9\u05dd \u05d9\u05e9\u05e8\u05d9\u05dd. \u05e2\u05d5\u05dc\u05dd \u05d1\u05d5 \u05de\u05ea\u05d1\u05e9\u05dc\u05d5\u05ea \u05e7\u05e0\u05d5\u05e0\u05d9\u05d5\u05ea \u05d1\u05e6\u05d5\u05e8\u05ea \u05e0\u05d9\u05e1\u05d9\u05d5\u05e0\u05d5\u05ea \u05e8\u05e6\u05d7 \u05d5\u05de\u05d2\u05e2\u05d9\u05dd \u05d0\u05e1\u05d5\u05e8\u05d9\u05dd.',
                u'tagline': None, u'title': u'\u05de\u05e9\u05d7\u05e7\u05d9 \u05d4\u05db\u05e1'}, u'ko': {
                u'overview': u'\uc218\uc2ed \ub144\uac04 \uc774\uc5b4\uc9c4 \uc5ec\ub984, \ud558\uc9c0\ub9cc \uc774\uc81c \uc601\uc6d0\ud788 \ub05d\ub098\uc9c0 \uc54a\uc744 \uaca8\uc6b8\uc774 \ub2e4\uac00\uc628\ub2e4.\n\n\uadf8\ub9ac\uace0... \ucca0\uc655\uc88c\ub97c \ub458\ub7ec\uc2fc \ud608\ud22c\uac00 \uc2dc\uc791\ub41c\ub2e4.\n\n\uc220\uc218\uc640 \ud0d0\uc695, \uc74c\ubaa8\uac00 \ub09c\ubb34\ud558\ub294 \ub0a8\ubd80\uc5d0\uc11c \uc57c\ub9cc\uc774 \uc228 \uc26c\ub294 \ub3d9\ubd80\uc758 \uad11\ud65c\ud55c \ub300\uc9c0, \uc5b4\ub460\uc758 \uc874\uc7ac\ub4e4\ub85c\ubd80\ud130 \uc655\uad6d\uc744 \uc9c0\ud0a4\uae30 \uc704\ud574 250M \ub192\uc774\uc758 \uc7a5\ubcbd\uc744 \uc313\uc740 \ubd81\ubd80\uc5d0 \uc774\ub974\uae30\uae4c\uc9c0 \ud3bc\uccd0\uc9c0\ub294 \ub300\uc11c\uc0ac\uc2dc.\n\n\uc655\ub4e4\uacfc \uc655\ube44\ub4e4, \uae30\uc0ac\ub4e4\uacfc \ubc30\uc2e0\uc790\ub4e4, \ubaa8\ub7b5\uac00\ub4e4, \uc601\uc8fc\ub4e4\uacfc \uc815\uc9c1\ud55c \uc778\ubb3c\ub4e4\uc774 \uc655\uc88c\uc758 \uac8c\uc784\uc744 \ubc8c\uc778\ub2e4.',
                u'tagline': None, u'title': u'\uc655\uc88c\uc758 \uac8c\uc784'}, u'sv': {
                u'overview': u'Serien utspelar sig p\xe5 den fiktiva kontinenten Westeros, oftast kallad "De sju konungarikena". Eddard "Ned" Stark bekymras av rykten fr\xe5n muren i norr d\xe5 han f\xe5r besked om att Jon Arryn, hans mentor och kungens hand, d\xf6tt och att kung Robert Baratheon \xe4r p\xe5 v\xe4g till Vinterhed. P\xe5 andra sidan havet smider exilprinsen Viseras Targaryen planer f\xf6r att \xe5terer\xf6vra De sju konungarikena.',
                u'tagline': None, u'title': u'Game of Thrones'},
            u'sk': {u'overview': u'', u'tagline': None, u'title': u'Hra o Tr\xf3ny'}, u'uk': {
                u'overview': u'\u0421\u0435\u0440\u0456\u0430\u043b "\u0413\u0440\u0430 \u041f\u0440\u0435\u0441\u0442\u043e\u043b\u0456\u0432" \u0437\u043d\u044f\u0442\u043e \u0437\u0430 \u0441\u044e\u0436\u0435\u0442\u043e\u043c \u0444\u0435\u043d\u0442\u0435\u0437\u0456-\u0431\u0435\u0441\u0442\u0441\u0435\u043b\u0435\u0440\u0456\u0432 "\u041f\u0456\u0441\u043d\u044f \u043b\u044c\u043e\u0434\u0443 \u0456 \u043f\u043e\u043b\u0443\u043c\'\u044f" \u0414\u0436\u043e\u0440\u0434\u0436\u0430 \u0420.\u0420. \u041c\u0430\u0440\u0442\u0456\u043d\u0430 (\u0432\u043e\u043b\u043e\u0434\u0430\u0440\u044f \u043f\u0440\u0435\u043c\u0456\u0439 \u0413\'\u044e\u0491\u043e \u0442\u0430 \u041d\u0435\u0431\'\u044e\u043b\u0430). \u0417 \u043c\u043e\u043c\u0435\u043d\u0442\u0443 \u0441\u0432\u043e\u0433\u043e \u0441\u0442\u0432\u043e\u0440\u0435\u043d\u043d\u044f "\u0413\u0440\u0430 \u041f\u0440\u0435\u0441\u0442\u043e\u043b\u0456\u0432" \u0441\u0442\u0430\u0432 \u043e\u0434\u043d\u0438\u043c \u0437 \u043d\u0430\u0439\u0434\u043e\u0440\u043e\u0436\u0447\u0438\u0445 \u0444\u0435\u043d\u0442\u0435\u0437\u0456-\u0441\u0435\u0440\u0456\u0430\u043b\u0456\u0432 \u0432 \u0456\u0441\u0442\u043e\u0440\u0456\u0457 \u0442\u0435\u043b\u0435\u0431\u0430\u0447\u0435\u043d\u043d\u044f. \u0426\u0435 \u043e\u0434\u043d\u0430 \u0437 \u043f\u0440\u0438\u0447\u0438\u043d, \u0437 \u044f\u043a\u043e\u0457 \u0442\u0435\u043b\u0435\u043a\u0440\u0438\u0442\u0438\u043a\u0438 \u0432\u0432\u0430\u0436\u0430\u044e\u0442\u044c \u0441\u0435\u0440\u0456\u0430\u043b \u0433\u043e\u043b\u043e\u0432\u043d\u0438\u043c \u043f\u0440\u0435\u0442\u0435\u043d\u0434\u0435\u043d\u0442\u043e\u043c \u043d\u0430 \u043b\u0430\u0432\u0440\u0438 "\u0412\u043e\u043b\u043e\u0434\u0430\u0440\u0430 \u043f\u0435\u0440\u0441\u0442\u0435\u043d\u0456\u0432" (\u044f\u043a \u043f\u0435\u0440\u0448\u043e\u0432\u0456\u0434\u043a\u0440\u0438\u0432\u0430\u0447\u0430 \u0436\u0430\u043d\u0440\u0443) \u043d\u0430 \u0442\u0435\u043b\u0435\u0431\u0430\u0447\u0435\u043d\u043d\u0456.\n\n\u041f\u043e\u0434\u0456\u0457 \u0441\u0435\u0440\u0456\u0430\u043b\u0443 \u0440\u043e\u0437\u0433\u043e\u0440\u0442\u0430\u044e\u0442\u044c\u0441\u044f \u0443 \u0444\u0435\u043d\u0442\u0435\u0437\u0456\u0439\u043d\u043e\u043c\u0443 \u0441\u0432\u0456\u0442\u0456, \u043c\u0435\u0448\u043a\u0430\u043d\u0446\u044f\u043c\u0438 \u044f\u043a\u043e\u0433\u043e - \u0430\u043c\u0431\u0456\u0446\u0456\u0439\u043d\u0456 \u0447\u043e\u043b\u043e\u0432\u0456\u043a\u0438 \u0442\u0430 \u0436\u0456\u043d\u043a\u0438, \u043a\u043e\u0442\u0440\u0438\u043c \u043f\u0440\u0438\u0442\u0430\u043c\u0430\u043d\u043d\u0456 \u044f\u043a \u0433\u0456\u0434\u043d\u0456\u0441\u0442\u044c, \u0442\u0430\u043a \u0456 \u0440\u043e\u0437\u043f\u0443\u0441\u0442\u0430. \u041d\u0430\u0439\u0446\u0456\u043d\u043d\u0456\u0448\u0430 \u0440\u0456\u0447 \u0443 \u0446\u044c\u043e\u043c\u0443 \u041a\u043e\u0440\u043e\u043b\u0456\u0432\u0441\u0442\u0432\u0456 \u2013 \u0417\u0430\u043b\u0456\u0437\u043d\u0438\u0439 \u0422\u0440\u043e\u043d. \u0422\u043e\u0439, \u0445\u0442\u043e \u043d\u0438\u043c \u0432\u043e\u043b\u043e\u0434\u0456\u0454, \u043e\u0442\u0440\u0438\u043c\u0443\u0454 \u043d\u0435\u0439\u043c\u043e\u0432\u0456\u0440\u043d\u0443 \u0432\u043b\u0430\u0434\u0443 \u0456 \u0432\u0438\u0437\u043d\u0430\u043d\u043d\u044f.\n\n\u0417\u0430 \u043f\u0430\u043d\u0443\u0432\u0430\u043d\u043d\u044f \u0443 \u041a\u043e\u0440\u043e\u043b\u0456\u0432\u0441\u0442\u0432\u0456 \u0431\u043e\u0440\u0435\u0442\u044c\u0441\u044f \u043e\u0434\u0440\u0430\u0437\u0443 \u0434\u0435\u043a\u0456\u043b\u044c\u043a\u0430 \u0432\u0456\u0434\u043e\u043c\u0438\u0445 \u0440\u043e\u0434\u0438\u043d. \u0421\u0435\u0440\u0435\u0434 \u043d\u0438\u0445: \u0431\u043b\u0430\u0433\u043e\u0440\u043e\u0434\u043d\u0456 \u0421\u0442\u0430\u0440\u043a\u0438, \u0437\u043c\u043e\u0432\u043d\u0438\u043a\u0438 \u041b\u0430\u043d\u043d\u0456\u0441\u0442\u0435\u0440\u0438, \u043f\u0440\u0438\u043d\u0446\u0435\u0441\u0430 \u0434\u0440\u0430\u043a\u043e\u043d\u0456\u0432 \u0414\u0435\u0439\u043d\u0435\u0440\u0456\u0441 \u0456 \u0457\u0457 \u0436\u043e\u0440\u0441\u0442\u043e\u043a\u0438\u0439 \u0431\u0440\u0430\u0442 \u0412\u0456\u0437\u0435\u0440\u0456\u0441.\n\n"\u0413\u0440\u0430 \u043f\u0440\u0435\u0441\u0442\u043e\u043b\u0456\u0432" \u2013 \u0446\u0435 \u0456\u0441\u0442\u043e\u0440\u0456\u044f \u043f\u0440\u043e \u0434\u0432\u043e\u0432\u043b\u0430\u0434\u0434\u044f \u0456 \u0437\u0440\u0430\u0434\u0443, \u0433\u0456\u0434\u043d\u0456\u0441\u0442\u044c \u0456 \u0431\u0435\u0437\u0447\u0435\u0441\u0442\u044f, \u0437\u0430\u0432\u043e\u044e\u0432\u0430\u043d\u043d\u044f \u0439 \u0442\u0440\u0456\u0443\u043c\u0444. \u0406 \u043a\u043e\u0436\u043d\u043e\u0433\u043e \u0443\u0447\u0430\u0441\u043d\u0438\u043a\u0430 \u0446\u0456\u0454\u0457 \u0433\u0440\u0438 \u043e\u0447\u0456\u043a\u0443\u0454 \u0430\u0431\u043e \u043f\u0435\u0440\u0435\u043c\u043e\u0433\u0430, \u0430\u0431\u043e \u0441\u043c\u0435\u0440\u0442\u044c.',
                u'tagline': None,
                u'title': u'\u0413\u0440\u0430 \u041f\u0440\u0435\u0441\u0442\u043e\u043b\u0456\u0432'}}

        task = execute_task('test_lookup_translations')
        assert len(task.entries) == 1
        entry = task.entries[0]

        assert entry['series_name'] == 'Game Of Thrones', 'series lookup failed'
        assert entry['trakt_translations'] == translations


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
                "overview": "1편의 엔딩 크레딧과 함께 인류를 구원해야 하는 자신의 운명을 받아들이며 하늘로 날아오른 네오(키아누 리브스). 내일 이 전쟁이 끝난다면, 한번 싸워 볼만하지 않을까...? 목숨도 걸어 볼만 하지 않을까...? 모피어스(로렌스 피쉬번)와 트리니티(캐리-앤 모스)가 전에 자신에게 던졌던 질문을 스스로에게 던져보는 네오는 마침내, 중대한 결정을 내린다.  시온이 컴퓨터 군단에게 장악될 위기에 처하면서, 네오는 자신의 능력에 대한 더 큰 통제력을 갖게 된다. 이제 몇시간 후면 지구상에 남은 인류 최후의 보루인 시온이 인간 말살을 목적으로 프로그래밍 된 센티넬 무리에 의해 짓밟히게 될 터... 그러나 시온의 시민들은 오라클의 예언이 이루어져 전쟁이 끝날 것이라는 모피어스의 신념에 용기를 얻고, 네오에게 모든 희망과 기대를 걸어보기로 한다.",
                "tagline": "",
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
                "overview": "Нео, Морфей та Трініті намагаються захистити підземне місто Зіон - останню схованку людей,  про існування якої нарешті дізнались безжалісні машини. Для цього героям потрібно проникнути у світ Матриці і перезавантажити її...",
                "tagline": "",
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
        task = execute_task('test_unicode')
        with Session() as session:
            r = session.query(TraktMovieSearchResult).all()
            assert len(r) == 1, 'Should have added a search result'
            assert r[0].search == '\u0417\u0435\u0440\u043a\u0430\u043b\u0430 Mirrors 2008'.lower(), \
                'The search result should be lower case'
        task = execute_task('test_unicode')
        with Session() as session:
            r = session.query(TraktMovieSearchResult).all()
            assert len(r) == 1, 'Should not have added a new row'
