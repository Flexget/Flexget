from __future__ import unicode_literals, division, absolute_import

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin


class TestSortByWeight(object):
    config = """
        tasks:
          test1:
            sort_by_weight:
              - field: quality
                weight: 100
              - field: content_size
                weight: 70
                upper_limit: 4000
              - field: score
                weight: 40
                delta_distance: 1
              - field: age
                weight: 15
                upper_limit: 30 days
                inverse: yes
              - field: date
                weight: 15
                inverse: yes
            mock:
              - {title: 'title1a', content_size:  400, score: 10,
                 date: !!timestamp 2016-1-1,
                 age: !Interval {text: '7 days'}}
              - {title: 'title1b', content_size:  450, score:  7,
                 date: !!timestamp '2016-2-14 21:59:43.10 -5',
                 age: !Interval {text: '15 days'},
                 quality: !Quality {text: 'webrip'}}
              - {title: 'title1c', content_size:  900, score:  7,
                 date: !!timestamp 2016-7-1,
                 age: !Interval {text: '60 days'},
                 quality: !Quality {text: 'HDTV'}}
              - {title: 'title2a', content_size: 1400, score:  1,
                 date: !!timestamp 2016-1-1,
                 age: !Interval {text: '3 days'},
                 quality: !Quality {text: '720p webrip'}}
              - {title: 'title2b', content_size:  900, score:  1,
                 date: !!timestamp 2016-4-1,
                 age: !Interval {text: '15 days'},
                 quality: !Quality {text: '720p webdl hi10p'}}
              - {title: 'title2c', content_size: 2300, score:  3,
                 date: !!timestamp '2016-2-14 21:59:43.10',
                 age: !Interval {text: '12 days'},
                 quality: !Quality {text: '720p webrip'}}
              - {title: 'title3a', content_size: 4600, score:  1,
                 date: !!timestamp 2016-1-1,
                 age: !Interval {text: '3 days'},
                 quality: !Quality {text: '1080p webrip'}}
              - {title: 'title3b', content_size: 5600, score:  5,
                 date: !!timestamp 2016-4-1,
                 age: !Interval {text: '15 days'},
                 quality: !Quality {text: '1080p webdl'}}
              - {title: 'title3c', content_size: 4000, score:  3,
                 date: !!timestamp '2016-2-14 21:59:43.10 -5',
                 age: !Interval {text: '90 days'},
                 quality: !Quality {text: '1080p blueray'}}
    """

    def test_sort_by_weight(self, execute_task):
        task = execute_task('test1')
        assert task.entries[0]['title'] == 'title3b' and task.entries[0]['sort_by_weight_sum'] == 197
        assert task.entries[1]['title'] == 'title3a' and task.entries[1]['sort_by_weight_sum'] == 177
        assert task.entries[2]['title'] == 'title3c' and task.entries[2]['sort_by_weight_sum'] == 162
        assert task.entries[3]['title'] == 'title2c' and task.entries[3]['sort_by_weight_sum'] == 121
        assert task.entries[4]['title'] == 'title2a' and task.entries[4]['sort_by_weight_sum'] == 101
        assert task.entries[5]['title'] == 'title2b' and task.entries[5]['sort_by_weight_sum'] == 96
        assert task.entries[6]['title'] == 'title1c' and task.entries[6]['sort_by_weight_sum'] == 93
        assert task.entries[7]['title'] == 'title1a' and task.entries[7]['sort_by_weight_sum'] == 88
        assert task.entries[8]['title'] == 'title1b' and task.entries[8]['sort_by_weight_sum'] == 82
