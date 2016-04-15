from __future__ import unicode_literals, division, absolute_import

import pytest

from flexget.plugins.parsers.parser_guessit import ParserGuessit
from flexget.plugins.parsers.parser_internal import ParserInternal


class TestParser(object):
    @pytest.fixture(scope='class', params=(ParserInternal, ParserGuessit), ids=['internal', 'guessit'])
    def parse(self, request):
        p = request.param()
        def parse(data, name=None, **kwargs):
            return p.parse_movie(data, name=name, **kwargs)
        return parse

    def test_parsing(self, parse):
        movie = parse('The.Matrix.1999.1080p.HDDVD.x264-FlexGet')
        assert movie.name == 'The Matrix', 'failed to parse %s (got %s)' % (movie.data, movie.name)
        assert movie.year == 1999, 'failed to parse year from %s' % movie.data

        movie = parse('WALL-E 720p BluRay x264-FlexGet')
        assert movie.name == 'WALL-E', 'failed to parse %s' % movie.data
        assert movie.quality.name == '720p bluray h264', 'failed to parse quality from %s' % movie.data

        movie = parse('The.Pianist.2002.HDDVD.1080p.DTS.x264-FlexGet')
        assert movie.name == 'The Pianist', 'failed to parse %s' % movie.data
        assert movie.year == 2002, 'failed to parse year from %s' % movie.data
        assert movie.quality.name == '1080p h264 dts', 'failed to parse quality from %s' % movie.data

        movie = parse("Howl's_Moving_Castle_(2004)_[720p,HDTV,x264,DTS]-FlexGet")
        assert movie.name == "Howl's Moving Castle", 'failed to parse %s' % movie.data
        assert movie.year == 2004, 'failed to parse year from %s' % movie.data
        assert movie.quality.name == '720p hdtv h264 dts', 'failed to parse quality from %s' % movie.data

        movie = parse('Coraline.3D.1080p.BluRay.x264-FlexGet')
        assert movie.name == 'Coraline', 'failed to parse %s' % movie.data
        assert movie.quality.name == '1080p bluray h264', 'failed to parse quality from %s' % movie.data

        movie = parse('Slumdog.Millionaire.DVDRip.XviD-FlexGet')
        assert movie.name == 'Slumdog Millionaire', 'failed to parse %s' % movie.data
        assert movie.quality.name == 'dvdrip xvid', 'failed to parse quality from %s' % movie.data

        movie = parse('TRON.Legacy.3D.2010.1080p.BluRay.Half.Over-Under.DTS.x264-FlexGet')
        assert movie.name == 'TRON Legacy', 'failed to parse %s' % movie.data

        movie = parse('[SomeThing]Up.2009.720p.x264-FlexGet')
        assert movie.name == 'Up', 'failed to parse %s (got %s)' % (movie.data, movie.name)
        assert movie.year == 2009, 'failed to parse year from %s' % movie.data

        movie = parse('[720p] A.Movie.Title.2013.otherstuff.x264')
        assert movie.name == 'A Movie Title', 'failed to parse %s (got %s)' % (movie.data, movie.name)
        assert movie.year == 2013, 'failed to parse year from %s' % movie.data
        assert movie.quality.name == '720p h264'
