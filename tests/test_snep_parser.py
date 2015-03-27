# -*- coding: utf8 -*-
from __future__ import unicode_literals, division, absolute_import

from flexget.utils.soup import get_soup
from flexget.utils.charts_snep import SnepChartsEntry
from flexget.utils.charts_snep import SnepChartsParser
from tests import use_vcr


class TestSnepParser(object):

    def test_offline_parser(self):
        soup = get_soup(open("../tests/data_charts_snep.html"))
        parser = SnepChartsParser()
        parser.parse(soup)
        TestSnepParser.subtest_parser(parser)


    # def test_online_parser(self):
    #     parser = SnepChartsParser()
    #     parser.retrieve_charts('all_album', 'week', 2015, 10)
    #     self.test_parser(parser)

    @staticmethod
    def subtest_parser(parser):
        """ Test a parser initialized with the content from
        http://www.snepmusique.com/tops-semaine/top-albums-fusionnes/?ye=2015&we=10
        :type parser: SnepChartsParser
        """

        assert (len(parser.charts_entries) == 200), "Expected 200 entries but parser produce %i entries." % len(parser.charts_entries)
        TestSnepParser.subtest_parse_entry(parser.charts_entries[42])

    @staticmethod
    def subtest_parse_entry(entry):
        """Test if entry is correctly parsed from the
        #43 of http://www.snepmusique.com/tops-semaine/top-albums-fusionnes/?ye=2015&we=10
        :param entry: SnepChartsEntry"""

        assert (entry != None), "Expected a charts entry but got None"
        assert entry.artist == "ZAZ"
        assert entry.company == "PLAY ON / PLAY ON"
        assert entry.title == "PARIS"
        assert entry.stat_position == 43
        assert entry.best_position == 2