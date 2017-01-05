from __future__ import unicode_literals, division, absolute_import

import datetime
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget.plugins.output.dump import dump
from flexget.utils.qualities import Quality

log = logging.getLogger('TestSortByWeight')

class TestSortByWeight(object):
    config = """
        tasks:
          test1:
            sort_by_weight:
              - field: quality
                weight: 100
              - field: content_size
                weight: 70
                upper_limit: 3500
              - field: score
                weight: 40
                delta_distance: 1
              - field: age
                weight: 20
                upper_limit: 60 days
                inverse: yes
            mock:
              - title: 'title1'
                content_size: 400
                date: !!timestamp 2002-12-14
                age: !Interval {text: '7 days'}
                score: 10
                quality: !Quality {text: '720p webrip hi10p'}
    """
#quality: !!python/object:flexget.utils.qualities.Quality {args: ['720p']}
    #quality: !Quality    {text: '720p webrip hi10p'}

    def test_sort_by_title(self, execute_task):
        log.info(execute_task)
        test = Quality()
        task = execute_task('test1')
        dump(task.entries)
        #assert task.entries[0]['title'] == 'A B C', 'Entries sorted alphabetically by title'
        #assert task.entries[1]['title'] == 'A P E', 'Entries sorted alphabetically by title'
        #assert task.entries[2]['title'] == 'B C D', 'Entries sorted alphabetically by title'
