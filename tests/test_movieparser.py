import pytest

from flexget.components.parsing.parsers.parser_guessit import ParserGuessit
from flexget.components.parsing.parsers.parser_internal import ParserInternal


class TestParser:
    @pytest.fixture(
        scope='class', params=(ParserInternal, ParserGuessit), ids=['internal', 'guessit']
    )
    def parse(self, request):
        p = request.param()

        def parse(data, name=None, **kwargs):
            return p.parse_movie(data, name=name, **kwargs)

        return parse

    def test_parsing(self, parse):
        movie = parse('The.Matrix.1999.1080p.HDDVD.x264-FlexGet')
        assert movie.name == 'The Matrix', f'failed to parse {movie.data} (got {movie.name})'
        assert movie.year == 1999, f'failed to parse year from {movie.data}'

        movie = parse('WALL-E 720p BluRay x264-FlexGet')
        assert movie.name == 'WALL-E', f'failed to parse {movie.data}'
        assert movie.quality.name == '720p bluray h264', (
            f'failed to parse quality from {movie.data}'
        )

        movie = parse('The.Pianist.2002.HDDVD.1080p.DTS.x264-FlexGet')
        assert movie.name == 'The Pianist', f'failed to parse {movie.data}'
        assert movie.year == 2002, f'failed to parse year from {movie.data}'
        assert movie.quality.name == '1080p h264 dts', f'failed to parse quality from {movie.data}'

        movie = parse("Howl's_Moving_Castle_(2004)_[720p,HDTV,x264,DTS]-FlexGet")
        assert movie.name == "Howl's Moving Castle", f'failed to parse {movie.data}'
        assert movie.year == 2004, f'failed to parse year from {movie.data}'
        assert movie.quality.name == '720p hdtv h264 dts', (
            f'failed to parse quality from {movie.data}'
        )

        movie = parse('Coraline.3D.1080p.BluRay.x264-FlexGet')
        assert movie.name == 'Coraline', f'failed to parse {movie.data}'
        assert movie.quality.name == '1080p bluray h264', (
            f'failed to parse quality from {movie.data}'
        )

        movie = parse('Slumdog.Millionaire.DVDRip.XviD-FlexGet')
        assert movie.name == 'Slumdog Millionaire', f'failed to parse {movie.data}'
        assert movie.quality.name == 'dvdrip xvid', f'failed to parse quality from {movie.data}'

        movie = parse('TRON.Legacy.3D.2010.1080p.BluRay.Half.Over-Under.DTS.x264-FlexGet')
        assert movie.name == 'TRON Legacy', f'failed to parse {movie.data}'

        movie = parse('[SomeThing]Up.2009.720p.x264-FlexGet')
        assert movie.name == 'Up', f'failed to parse {movie.data} (got {movie.name})'
        assert movie.year == 2009, f'failed to parse year from {movie.data}'

        movie = parse('[720p] A.Movie.Title.2013.otherstuff.x264')
        assert movie.name == 'A Movie Title', f'failed to parse {movie.data} (got {movie.name})'
        assert movie.year == 2013, f'failed to parse year from {movie.data}'
        assert movie.quality.name == '720p h264'

    def test_multiple_property_values(self, parse):
        """Test correct parsing for title's with multiple propertie definitions."""
        movie = parse(
            name='FlexGet',
            data='FlexGet (premiere 2018)(2016/MHD/1080P/AC3 5.1/DUAL/SUB/bluray/Webrip)',
        )
        assert movie.valid
        assert movie.year == 2018
        assert movie.quality.source == 'bluray'
