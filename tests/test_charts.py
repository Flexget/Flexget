# -*- coding: utf8 -*-
from __future__ import unicode_literals, division, absolute_import
import datetime

from flexget import plugin
from flexget.event import event
from flexget.plugins.filter.charts import ChartsConnector, ChartsRelease, ChartsEntry, charts_connectors
from tests import FlexGetBase


class MockConnector(ChartsConnector):
    def __init__(self):
        self.call_flag = False
        self.release = None

    @property
    def organization(self):
        return 'mock'

    def retrieve_charts(self, charts_type='radio', date_interval='week', **kargs):
        self.call_flag = True
        return self.release

@event('plugin.register')
def register_plugin():
    plugin.register(MockConnector, 'charts_connector_mock', groups=['charts_connector'], api_ver=2)


class TestCharts(FlexGetBase):
    __yaml__ = """
        tasks:
          caching:
            charts:
              provider : mock
              category : radio

          filtering:
            disable: builtins
            mock:
              - {title: 'Zeus - THE best sound 2014 FLAC'}
              - {title: 'Devil - The worst sound 2010 mp3'}
              - {title: 'Uncharted - Hello world 128kbps'}
            charts:
              provider : mock
              category : radio
              max_best_rank : 5
              min_charted_weeks : 4
    """

    def test_connector_registering(self):
        mock_connector = charts_connectors.get('mock')
        assert mock_connector is not None
        assert mock_connector.organization == 'mock', "Charts connector registering fails"

    def test_caching(self):
        mock_connector = charts_connectors.get('mock')
        """:type mock_connector: MockConnector"""

        mock_connector.call_flag = False
        mock_connector.release = ChartsRelease()
        mock_connector.release.expires = datetime.datetime.max
        mock_connector.release.entries.append(ChartsEntry(
            artist="ZAZ",
            title="PARIS",
            rank=43,
            best_rank=2,
            charted_weeks=15))

        self.execute_task('caching')
        assert mock_connector.call_flag, 'Mock connector never used'
        mock_connector.call_flag = False
        self.execute_task('caching')
        assert not mock_connector.call_flag, 'Mock connector used instead cached provider'

    def test_filtering(self):
        mock_connector = charts_connectors.get('mock')
        """:type mock_connector: MockConnector"""

        mock_connector.call_flag = False
        mock_connector.release = ChartsRelease()
        mock_connector.release.expires = datetime.datetime.max
        mock_connector.release.entries.append(ChartsEntry(
            artist="Zeus",
            title="THE best sound",
            best_rank=1,
            rank=10,
            charted_weeks=100))
        mock_connector.release.entries.append(ChartsEntry(
            artist="Devil",
            title="The WORST sound",
            best_rank=150,
            rank=1500,
            charted_weeks=3))

        def my_assert(task):
            assert task.find_entry('accepted', title='Zeus - THE best sound 2014 FLAC')
            assert task.find_entry('undecided', title='Devil - The worst sound 2010 mp3')
            assert task.find_entry('undecided', title='Uncharted - Hello world 128kbps')

        self.execute_task('filtering')
        my_assert(self.task)

        # A second time for cache based
        self.execute_task('filtering')
        my_assert(self.task)