from flexget.utils.titles import MovieParser, ParseWarning


class TestMovieParser:

    def parse(self, data):
        movieparser = MovieParser()
        movieparser.data = data
        movieparser.parse()
        return movieparser

    def test_parsing(self):
        movie = self.parse('The.Matrix.1999.1080p.HDDVD.x264-FlexGet')
        assert movie.name == 'The Matrix', 'failed to parse %s (got %s)' % (movie.data, movie.name)
        assert movie.year == 1999, 'failed to parse year from %s' % movie.data

        movie = self.parse('WALL-E 720p BluRay x264-FlexGet')
        assert movie.name == 'WALL-E', 'failed to parse %s' % movie.data
        assert movie.quality == '720p bluray', 'failed to parse quality from %s' % movie.data

        movie = self.parse('The.Pianist.2002.HDDVD.1080p.DTS.x264-FlexGet')
        assert movie.name == 'The Pianist', 'failed to parse %s' % movie.data
        assert movie.year == 2002, 'failed to parse year from %s' % movie.data
        assert movie.quality == '1080p', 'failed to parse quality from %s' % movie.data

        movie = self.parse("Howl's_Moving_Castle_(2004)_[720p,HDTV,x264,DTS]-FlexGet")
        assert movie.name == "Howl's Moving Castle", 'failed to parse %s' % movie.data
        assert movie.year == 2004, 'failed to parse year from %s' % movie.data
        assert movie.quality == '720p', 'failed to parse quality from %s' % movie.data

        movie = self.parse('Coraline.3D.1080p.BluRay.x264-FlexGet')
        assert movie.name == 'Coraline', 'failed to parse %s' % movie.data
        assert movie.quality == '1080p bluray', 'failed to parse quality from %s' % movie.data

        movie = self.parse('Slumdog.Millionaire.DVDRip.XviD-FlexGet')
        assert movie.name == 'Slumdog Millionaire', 'failed to parse %s' % movie.data
        assert movie.quality == 'dvdrip', 'failed to parse quality from %s' % movie.data

        movie = self.parse('TRON.Legacy.3D.2010.1080p.BluRay.Half.Over-Under.DTS.x264-FlexGet')
        assert movie.name == 'TRON Legacy', 'failed to parse %s' % movie.data
