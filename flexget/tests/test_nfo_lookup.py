#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest


@pytest.mark.online
class TestNfoLookupWithMovies(object):
    base = "nfo_lookup_test_dir/"
    config = """
        tasks:
          test_1:  # Only ID
            filesystem:
              path: {0}/test_1
              mask: '*.mkv'
            nfo_lookup: yes
            imdb_lookup: yes
          test_2:  # ID and Title
            filesystem:
              path: {0}/test_2
              mask: '*.mkv'
            nfo_lookup: yes
          test_3:  # ID, Title and Original Title
            filesystem:
              path: {0}/test_3
              mask: '*.mkv'
            nfo_lookup: yes
          test_4:  # ID, Title and Plot
            filesystem:
              path: {0}/test_4
              mask: '*.mkv'
            nfo_lookup: yes
          test_5:  # ID and genres
            filesystem:
              path: {0}/test_5
              mask: '*.mkv'
            nfo_lookup: yes
          test_6:  # No nfo file is provided
            filesystem:
              path: {0}/test_6
              mask: '*.mkv'
            nfo_lookup: yes
            imdb_lookup: yes
          test_7:  # Use the nfo_lookup plugin with entries not from the filesystem plugin
            mock:
              - {{title: 'A Bela e a Fera'}}
            nfo_lookup: yes
            imdb_lookup: yes
          test_8:  # Call the plugin twice. The second time won't do anything
            mock:
              - {{title: 'A Bela e a Fera', filename: 'beast_beauty.mkv', nfo_id: 'tt2316801'}}
            nfo_lookup: yes
          test_9:  # Disabled configuration
            filesystem:
              path: {0}/test_9
              mask: '*.mkv'
            nfo_lookup: no
    """.format(base)

    def test_nfo_with_only_id(self, execute_task):
        # run the task
        task = execute_task('test_1')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry. In this test the info file only
            # has the 'id' field
            nfo_keys = sorted([i for i in entry.keys() if i[:3] == 'nfo'])
            assert nfo_keys == [u'nfo_id']

            assert entry['title'] == u'A Bela e a Fera'  # This will be == to filename

            # Check that the 'nfo_id' field is set to the correct movie
            assert entry['nfo_id'] == 'tt2316801'
            assert entry['imdb_id'] == 'tt2316801'

            # The imdb_lookup plugin was able to get the correct movie metadata
            # even though there are many versions of (Beauty and the
            # Beast). That is because the nfo_lookup plugin sets the 'imdb_id'
            # field in the entry.
            assert entry['imdb_name'] == 'Beauty and the Beast'
            assert entry['imdb_original_name'] == u"La belle et la bête"
            assert entry['imdb_year'] == 2014
            assert entry['imdb_genres'] == [u'fantasy', u'romance']

    def test_nfo_with_id_title(self, execute_task):
        # run the task
        task = execute_task('test_2')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry.keys() if i[:3] == 'nfo'])
            assert nfo_keys == [u'nfo_id', u'nfo_title']

            assert entry['title'] == u'Bela e Fera'  # This will be == to filename

            # Check that the 'nfo_id' field is set to the correct movie
            assert entry['nfo_id'] == 'tt2316801'
            assert entry['nfo_title'] == 'A Bela e a Fera'
            assert entry['imdb_id'] == 'tt2316801'

    def test_nfo_with_id_title_originaltitle(self, execute_task):
        # run the task
        task = execute_task('test_3')
        for entry in task.entries:
            assert entry['title'] == u'A Bela e a Fera'  # This will be == to filename

            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry.keys() if i[:3] == 'nfo'])
            assert nfo_keys == [u'nfo_id', u'nfo_originaltitle', u'nfo_title']

            assert entry['title'] == u'A Bela e a Fera'  # This will be == to filename

            # Check that the 'nfo_id' field is set to the correct movie
            assert entry['nfo_id'] == 'tt2316801'
            assert entry['nfo_title'] == 'A Bela e a Fera'
            assert entry['nfo_originaltitle'] == 'La belle et la bête (French)'
            assert entry['imdb_id'] == 'tt2316801'

    def test_nfo_with_id_title_plot(self, execute_task):
        # run the task
        task = execute_task('test_4')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry.keys() if i[:3] == 'nfo'])
            assert nfo_keys == [u'nfo_id', u'nfo_plot', u'nfo_title']

            assert entry['title'] == u'A Bela e a Fera'  # This will be == to filename

            # Check that the 'nfo_id' field is set to the correct movie
            assert entry['nfo_id'] == 'tt2316801'
            assert entry['nfo_title'] == 'A Bela e a Fera'
            assert entry['nfo_plot'] == u"Um romance inesperado floresce depois que a filha mais nova de um mercador em dificuldades se oferece para uma misteriosa besta com a qual seu pai ficou endividado."
            assert entry['imdb_id'] == 'tt2316801'

    def test_nfo_with_id_genres(self, execute_task):
        # run the task
        task = execute_task('test_5')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry.keys() if i[:3] == 'nfo'])
            assert nfo_keys == [u'nfo_genre', u'nfo_id']

            # Check that the 'nfo_id' field is set to the correct movie
            assert entry['nfo_id'] == 'tt2316801'
            assert entry['nfo_genre'] == ['Fantasia', 'Romance']
            assert entry['imdb_id'] == 'tt2316801'

    def test_nfo_with_no_nfo_file(self, execute_task):
        # run the task
        task = execute_task('test_6')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry.keys() if i[:3] == 'nfo'])
            assert nfo_keys == []

            assert entry['title'] == u'A Bela e a Fera'  # This will be == to filename

            # Since there is no nfo file then an IMDB search is performed only
            # with the filename. That means that we will get a different
            # version of the "Beauty and the Beast" movie, with a different ID
            assert entry['imdb_id'] != 'tt2316801'
            # Filename (it is in portuguese)

            # IMDB is able to find the movie from the Portuguese title,
            # although it is not the correct one
            assert entry['imdb_name'] == 'Beauty and the Beast'

    def test_nfo_lookup_without_filesystem(self, execute_task):
        # run the task
        task = execute_task('test_7')
        # This is the same as not having an nfo file
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry.keys() if i[:3] == 'nfo'])
            assert nfo_keys == []

            # Since there is no nfo file then an IMDB search is performed only
            # with the filename. That means that we will get a different
            # version of the "Beauty and the Beast" movie, with a different ID
            assert entry['imdb_id'] != 'tt2316801'
            # Filename (it is in portuguese)
            assert entry['title'] == u'A Bela e a Fera'  # This will be == to filename
            # IMDB is able to find the movie from the Portuguese title,
            # although it is not the correct one
            assert entry['imdb_name'] == 'Beauty and the Beast'

    def test_nfo_lookup_with_already_processed_entry(self, execute_task):
        # run the task
        task = execute_task('test_8')
        for entry in task.entries:
            # Since the entry was not processed again then no new fields
            # besides the fields added by the mock configiration in test_8
            # should be present.
            keys = sorted(entry.keys())
            assert entry['nfo_id'] == 'tt2316801'

            # NOTE: The mock configuration in test_8 only specify the fields
            # "title", "filename" and "nfo_id". The other fields in the assert
            # below are added by the testing framework and the mock plugin. If
            # this change in any future version make the necessary changes in
            # the assert below.
            assert keys == sorted([u'title', u'filename', u'nfo_id',
                                   u'task', u'url', u'original_url', u'quality'])

    def test_nfo_lookup_with_disabled_configuration(self, execute_task):
        # run the task
        task = execute_task('test_9')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = [i for i in entry.keys() if i[:3] == 'nfo']
            assert nfo_keys == []

            imdb_keys = [i for i in entry.keys() if i[:4] == 'imdb']
            assert imdb_keys == []


# TODO: Test with other fields, such as actors


# TODO: Test with series
