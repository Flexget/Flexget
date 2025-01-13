import pytest


@pytest.mark.online
class TestNfoLookupWithMovies:
    base = "nfo_lookup_test_dir/"
    config = f"""
        tasks:
          test_1:  # Only ID
            filesystem:
              path: {base}/test_1
              mask: '*.mkv'
            nfo_lookup: yes
            imdb_lookup: yes
          test_2:  # ID and Title
            filesystem:
              path: {base}/test_2
              mask: '*.mkv'
            nfo_lookup: yes
          test_3:  # ID, Title and Original Title
            filesystem:
              path: {base}/test_3
              mask: '*.mkv'
            nfo_lookup: yes
          test_4:  # ID, Title and Plot
            filesystem:
              path: {base}/test_4
              mask: '*.mkv'
            nfo_lookup: yes
          test_5:  # ID and genres
            filesystem:
              path: {base}/test_5
              mask: '*.mkv'
            nfo_lookup: yes
          test_6:  # No nfo file is provided
            filesystem:
              path: {base}/test_6
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
              path: {base}/test_9
              mask: '*.mkv'
            nfo_lookup: no
          test_10:  # Test with ID, title and actors
            filesystem:
              path: {base}/test_10
              mask: '*.mkv'
            nfo_lookup: yes
          test_11:  # Test with all fields
            filesystem:
              path: {base}/test_11
              mask: '*.mkv'
            nfo_lookup: yes
          test_12:  # Test with an invalid file
            filesystem:
              path: {base}/test_12
              mask: '*.mkv'
            nfo_lookup: yes
          test_13:  # Test with an nfo file containing invalid IMDB ID
            filesystem:
              path: {base}/test_13
              mask: '*.mkv'
            nfo_lookup: yes
    """

    def test_nfo_with_only_id(self, execute_task):
        task = execute_task('test_1')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry. In this test the info file only has the 'id' field
            nfo_keys = sorted([i for i in entry if i[:3] == 'nfo'])
            assert nfo_keys == ['nfo_id']

            assert entry['title'] == 'A Bela e a Fera'  # This will be == to filename

            # Check that the 'nfo_id' field is set to the correct movie
            assert entry['nfo_id'] == 'tt2316801'
            assert entry['imdb_id'] == 'tt2316801'

            # The imdb_lookup plugin was able to get the correct movie metadata even though there are many versions of
            # (Beauty and the Beast). That is because the nfo_lookup plugin sets the 'imdb_id' field in the entry.
            assert entry['imdb_name'] == 'Beauty and the Beast'
            assert entry['imdb_original_name'] == "La belle et la bête"
            assert entry['imdb_year'] == 2014
            assert entry['imdb_genres'] == ['drama', 'family', 'fantasy', 'romance', 'thriller']

    def test_nfo_with_id_title(self, execute_task):
        task = execute_task('test_2')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry if i[:3] == 'nfo'])
            assert nfo_keys == ['nfo_id', 'nfo_title']

            assert entry['title'] == 'Bela e Fera'  # This will be == to filename

            # Check that the 'nfo_id' field is set to the correct movie
            assert entry['nfo_id'] == 'tt2316801'
            assert entry['nfo_title'] == 'A Bela e a Fera'
            assert entry['imdb_id'] == 'tt2316801'

    def test_nfo_with_id_title_originaltitle(self, execute_task):
        task = execute_task('test_3')
        for entry in task.entries:
            assert entry['title'] == 'A Bela e a Fera'  # This will be == to filename

            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry if i[:3] == 'nfo'])
            assert nfo_keys == ['nfo_id', 'nfo_originaltitle', 'nfo_title']

            assert entry['title'] == 'A Bela e a Fera'  # This will be == to filename

            # Check that the 'nfo_id' field is set to the correct movie
            assert entry['nfo_id'] == 'tt2316801'
            assert entry['nfo_title'] == 'A Bela e a Fera'
            assert entry['nfo_originaltitle'] == 'La belle et la bête (French)'
            assert entry['imdb_id'] == 'tt2316801'

    def test_nfo_with_id_title_plot(self, execute_task):
        task = execute_task('test_4')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry if i[:3] == 'nfo'])
            assert nfo_keys == ['nfo_id', 'nfo_plot', 'nfo_title']

            assert entry['title'] == 'A Bela e a Fera'  # This will be == to filename

            # Check that the 'nfo_id' field is set to the correct movie
            assert entry['nfo_id'] == 'tt2316801'
            assert entry['nfo_title'] == 'A Bela e a Fera'
            assert entry['nfo_plot'] == (
                "Um romance inesperado floresce depois que a filha mais nova de um mercador "
                "em dificuldades se oferece para uma misteriosa besta com a qual seu pai "
                "ficou endividado."
            )
            assert entry['imdb_id'] == 'tt2316801'

    def test_nfo_with_id_genres(self, execute_task):
        task = execute_task('test_5')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry if i[:3] == 'nfo'])
            assert nfo_keys == ['nfo_genre', 'nfo_id']

            # Check that the 'nfo_id' field is set to the correct movie
            assert entry['nfo_id'] == 'tt2316801'
            assert entry['nfo_genre'] == ['Fantasia', 'Romance']
            assert entry['imdb_id'] == 'tt2316801'

    def test_nfo_with_no_nfo_file(self, execute_task):
        task = execute_task('test_6')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry if i[:3] == 'nfo'])
            assert nfo_keys == []

            assert entry['title'] == 'A Bela e a Fera'  # This will be == to filename

            # Since there is no nfo file then an IMDB search is performed only with the filename. That means that we
            # will get a different version of the "Beauty and the Beast" movie, with a different ID
            assert entry['imdb_id'] != 'tt2316801'

            # IMDB is able to find the movie from the Portuguese title, although it is not the correct one
            assert entry['imdb_name'] == 'Beauty and the Beast'

    def test_nfo_lookup_without_filesystem(self, execute_task):
        task = execute_task('test_7')
        # This is the same as not having an nfo file
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry if i[:3] == 'nfo'])
            assert nfo_keys == []

            # Since there is no nfo file then an IMDB search is performed only with the filename. That means that we
            # will get a different version of the "Beauty and the Beast" movie, with a different ID
            assert entry['imdb_id'] != 'tt2316801'
            # Filename (it is in portuguese)
            assert entry['title'] == 'A Bela e a Fera'  # This will be == to filename
            # IMDB is able to find the movie from the Portuguese title, although it is not the correct one
            assert entry['imdb_name'] == 'Beauty and the Beast'

    def test_nfo_lookup_with_already_processed_entry(self, execute_task):
        task = execute_task('test_8')
        for entry in task.entries:
            # Since the entry was not processed again then no new fields besides the fields added by the mock
            # configiration in test_8 should be present.
            keys = sorted(entry.keys())
            assert entry['nfo_id'] == 'tt2316801'

            # NOTE: The mock configuration in test_8 only specify the fields "title", "filename" and "nfo_id". The other
            # fields in the assert below are added by the testing framework and the mock plugin. If this change in any
            # future version make the necessary changes in the assert below.
            assert keys == sorted(
                [
                    '_backlog_snapshot',
                    'title',
                    'original_title',
                    'filename',
                    'media_id',
                    'nfo_id',
                    'task',
                    'url',
                    'original_url',
                    'quality',
                ]
            )

    def test_nfo_lookup_with_disabled_configuration(self, execute_task):
        task = execute_task('test_9')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = [i for i in entry if i[:3] == 'nfo']
            assert nfo_keys == []

            imdb_keys = [i for i in entry if i[:4] == 'imdb']
            assert imdb_keys == []

    def test_nfo_with_id_title_and_actors(self, execute_task):
        task = execute_task('test_10')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry if i[:3] == 'nfo'])
            assert nfo_keys == ['nfo_actor', 'nfo_id', 'nfo_title']

            # Check that the 'nfo_id' field is set to the correct movie
            assert entry['nfo_id'] == 'tt2316801'
            assert entry['nfo_title'] == 'A Bela e a Fera'

            # Check the actors. They are in the same order from the nfo file
            assert entry['nfo_actor'][0]['name'] == "Vincent Cassel"
            assert entry['nfo_actor'][0]['role'] == "La bête"

            assert entry['nfo_actor'][1]['name'] == "Léa Seydoux"
            assert entry['nfo_actor'][1]['role'] == "La belle"

            assert entry['nfo_actor'][2]['name'] == "André Dussollier"
            assert entry['nfo_actor'][2]['role'] == "Belle's father"

            assert entry['nfo_actor'][3]['name'] == "Eduardo Noriega"
            assert entry['nfo_actor'][3]['role'] == "Perducas"

            assert entry['nfo_actor'][4]['name'] == "Myriam Charleins"
            assert entry['nfo_actor'][4]['role'] == "Astrid"

            # assert entry['nfo_genre'] == ['Fantasia', 'Romance']
            assert entry['imdb_id'] == 'tt2316801'

    def test_nfo_with_all_fields(self, execute_task):
        task = execute_task('test_11')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry
            nfo_keys = sorted([i for i in entry if i[:3] == 'nfo'])
            assert nfo_keys == [
                'nfo_actor',
                'nfo_country',
                'nfo_director',
                'nfo_genre',
                'nfo_id',
                'nfo_originaltitle',
                'nfo_plot',
                'nfo_rating',
                'nfo_runtime',
                'nfo_studio',
                'nfo_thumb',
                'nfo_title',
                'nfo_trailer',
                'nfo_votes',
                'nfo_year',
            ]

            # Check that the 'nfo_id' field is set to the correct movie
            assert entry['nfo_id'] == 'tt2316801'
            assert entry['nfo_title'] == 'A Bela e a Fera'

            # Check the actors. They are in the same order from the nfo file
            assert entry['nfo_actor'][0]['name'] == "Vincent Cassel"
            assert entry['nfo_actor'][0]['role'] == "La bête"

            assert entry['nfo_actor'][1]['name'] == "Léa Seydoux"
            assert entry['nfo_actor'][1]['role'] == "La belle"

            assert entry['nfo_actor'][2]['name'] == "André Dussollier"
            assert entry['nfo_actor'][2]['role'] == "Belle's father"

            assert entry['nfo_actor'][3]['name'] == "Eduardo Noriega"
            assert entry['nfo_actor'][3]['role'] == "Perducas"

            assert entry['nfo_actor'][4]['name'] == "Myriam Charleins"
            assert entry['nfo_actor'][4]['role'] == "Astrid"

            assert entry['nfo_country'] == ["France", "Germany"]
            # Single director, but still a list
            assert entry['nfo_director'] == ["Christophe Gans"]
            assert entry['nfo_genre'] == ["Fantasia", "Romance"]
            assert entry['nfo_originaltitle'] == "La Belle et la Bête"
            assert entry['nfo_plot'] == (
                "Um romance inesperado floresce depois que a filha mais nova de um mercador "
                "em dificuldades se oferece para uma misteriosa besta com a qual seu pai "
                "ficou endividado."
            )
            assert entry['nfo_rating'] == "6"
            assert entry['nfo_runtime'] == "153"
            assert entry['nfo_studio'] == ["Canal Plus", "Studio Babelsberg", "Eskwad"]

            # There are 3 'thumb's in the nfo file
            assert len(entry['nfo_thumb']) == 3

            assert entry['nfo_trailer'] == "http://www.youtube.com/watch?v=P-WF6ugqIY8"

            assert entry['nfo_votes'] == '210'
            assert entry['nfo_year'] == '2014'

            # assert entry['nfo_genre'] == ['Fantasia', 'Romance']
            assert entry['imdb_id'] == 'tt2316801'

    def test_nfo_with_invalid_file(self, execute_task):
        task = execute_task('test_12')
        for entry in task.entries:
            # Get all 'nfo' keys in the entry. In this test the info file only has the 'id' field
            nfo_keys = sorted([i for i in entry if i[:3] == 'nfo'])
            # Since the nfo file is invalid (there was some parse error) then there is no nfo fields.
            assert nfo_keys == []

    def test_nfo_with_invalid_imdb_id(self, execute_task):
        task = execute_task('test_13')
        for entry in task.entries:
            nfo_keys = sorted([i for i in entry if i[:3] == 'nfo'])
            assert nfo_keys == ['nfo_id', 'nfo_title']

            # Since the id in the nfo file is not a valid IMDB Id then it was not added to the entry
            imdb_keys = sorted([i for i in entry if i[:4] == 'imdb'])
            assert imdb_keys == []

            assert entry['title'] == 'A Bela e a Fera'  # This will be == to filename

            # Valid IMDB IDs for titles are formed by 'tt' and 7 digits
            # Not that even if the value
            # in the "id" tag is not a valid IMDB ID it is still added as the
            # 'nfo_id'. However, it is not added as the 'imdb_id' field.
            assert entry['nfo_id'] == 'tt1234'
            assert entry['nfo_title'] == 'A Bela e a Fera'


# TODO: Test with series
