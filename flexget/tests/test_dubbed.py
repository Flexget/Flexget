from flexget import plugin
from flexget.entry import Entry


class TestDubbed:
    config = """
        tasks:
            dubbed1:
                mock:
                    - { title: "Attack on Titan S01E01 French 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p Japanese", url: "http://mock.url/file2.torrent" }


                dubbed:
                    languages:
                        - "japanese"
                    action:
                        japanese: "accept"
                        default: "reject"

                series:
                    - Attack on Titan:
                        identified_by: ep



            dubbed2:
                mock:
                    - { title: "Show S01E01 Tuga 720p", trakt_series_language:"english", url:"http://mock.url/file2.torrent" }
                    - { title: "Show S01E01 720p",  trakt_series_language:"english", url:"http://mock.url/file2.torrent" }

                dubbed:
                    languages_synonyms:
                        portuguese:
                            - tuga
                    languages:
                        - "trakt_series_language"
                    action:
                        portuguese: "accept"
                        default: "reject"

                series:
                    - Show:
                        identified_by: ep


            dubbed3:
                mock:
                    - { title: "Movie French 720p", movie_name: "Movie", trakt_language: "english", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie Spanish 720p", movie_name: "Movie",  trakt_language: "english", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie English 720p", movie_name: "Movie",  trakt_language: "english", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie 720p", movie_name: "Movie",  trakt_language: "english", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie En 720p", movie_name: "Movie",  trakt_language: "english", url:"http://mock.url/file2.torrent" }

                dubbed:
                    languages:
                        - "trakt_language"
                    action: reject

            dubbed4:
                mock:
                    - { title: "Movie Dub 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie Dubbed 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie PT_BR 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie French 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }

                dubbed:
                    action: accept
    """

    def test_force_native(self, execute_task):
        task = execute_task('dubbed1')
        assert len(task.accepted) == 2
        assert task.accepted[0]['title'] == 'Attack on Titan S01E01 720p WEBRip'
        assert task.accepted[1]['title'] == 'Attack on Titan S01E01 720p Japanese'

    def test_force_synonym(self, execute_task):
        task = execute_task('dubbed2')
        assert len(task.accepted) == 1
        assert task.accepted[0]['title'] == 'Show S01E01 Tuga 720p'

    def test_get_native(self, execute_task):
        task = execute_task('dubbed3')
        assert len(task.accepted) == 3

        expected = ['Movie English 720p', 'Movie 720p', 'Movie En 720p']

        assert task.accepted[0]['title'] in expected
        assert task.accepted[1]['title'] in expected
        assert task.accepted[2]['title'] in expected

    def test_get_dubbed(self, execute_task):
        task = execute_task('dubbed4')
        assert len(task.accepted) == 4

        expected = ['Movie Dub 720p', 'Movie Dubbed 720p', 'Movie PT_BR 720p', 'Movie French 720p']

        assert task.accepted[0]['title'] in expected
        assert task.accepted[1]['title'] in expected
        assert task.accepted[2]['title'] in expected
        assert task.accepted[3]['title'] in expected