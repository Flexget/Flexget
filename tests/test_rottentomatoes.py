from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestRottenTomatoesLookup(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              # tests search
              - {title: 'Toy Story'}
              - {title: 'The Matrix'}
              - {title: 'Star Wars: Episode I - The Phantom Menace (in 3D)'}
              # tests direct id
              - {title: '[Group] Taken 720p', rt_id: 770680780}
              # tests title + year
              - {title: 'Rush.Hour[1998]1080p[Eng]-FOO'}
              # test short title, with repack and without year
              - {title: 'Up.REPACK.720p.Bluray.x264-FlexGet'}
            rottentomatoes_lookup: yes
    """

    @attr(online=True)
    def test_rottentomatoes_lookup(self):
        self.execute_task('test')
        # check that these were created
        assert self.task.find_entry(rt_name='Toy Story', rt_year=1995, rt_id=9559, imdb_id='tt0114709'), \
            'Didn\'t populate RT info for Toy Story'
        assert self.task.find_entry(imdb_id='tt0114709'), \
            'Didn\'t populate imdb_id info for Toy Story'
        assert self.task.find_entry(rt_name='The Matrix', rt_year=1999, rt_id=12897, imdb_id='tt0133093'), \
            'Didn\'t populate RT info for The Matrix'
        assert self.task.find_entry(rt_name='Star Wars: Episode I - The Phantom Menace',
                                    rt_year=1999, rt_id=10008), \
            'Didn\'t populate RT info for Star Wars: Episode I - The Phantom Menace (in 3D)'
        assert self.task.find_entry(rt_name='Taken', rt_year=2008, rt_id=770680780), \
            'Didn\'t populate RT info for Taken'
        assert self.task.find_entry(rt_name='Rush Hour', rt_year=1998, rt_id=10201), \
            'Didn\'t populate RT info for Rush Hour'
        assert self.task.find_entry(rt_name='Up', rt_year=2009, rt_id=770671912), \
            'Didn\'t populate RT info for Up'
