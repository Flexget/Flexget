class TestTranslationsFilter:
    config = """
        tasks:
            dubbed1:
                mock:
                    - { title: "Attack on Titan S01E01 DUBFrench DUBItalian 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 French 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p Japanese", url: "http://mock.url/file2.torrent" }


                translations:
                    languages:
                        - "japanese"
                    dubbed:
                        japanese: "accept"
                        default: "reject"

                series:
                    - Attack on Titan:
                        identified_by: ep



            dubbed2:
                mock:
                    - { title: "Show S01E01 Tuga 720p", trakt_series_language:"english", url:"http://mock.url/file2.torrent" }
                    - { title: "Show S01E01 720p",  trakt_series_language:"english", url:"http://mock.url/file2.torrent" }

                translations:
                    languages_synonyms:
                        portuguese:
                            - tuga
                    language_fields:
                        - "trakt_series_language"
                    dubbed:
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

                translations:
                    language_fields:
                        - "trakt_language"
                    dubbed: reject

            dubbed_accept:
                mock:
                    - { title: "Movie Dub 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie Dubbed 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie PT_BR 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie French 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }

                translations: accept

            dubbed_reject:
                mock:
                    - { title: "Movie Dub 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie Dubbed 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie PT_BR 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }
                    - { title: "Movie French 720p", movie_name: "Movie", url:"http://mock.url/file2.torrent" }

                translations: reject

            subbed1:
                mock:
                    - { title: "Attack on Titan S01E01 SubFrench SubItalian 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 SubEnglish 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p SubJapanese", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p Subbed", url: "http://mock.url/file2.torrent" }


                translations:
                    languages:
                        - "japanese"
                    dubbed: reject
                    subbed:
                        english: "do_nothing"
                        default: "reject"

                series:
                    - Attack on Titan:
                        parse_only: yes
                        identified_by: ep

            subbed2:
                mock:
                    - { title: "Attack on Titan S01E01 SubFrench SubItalian 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 SubEnglish 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p SubJapanese", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p Subbed", url: "http://mock.url/file2.torrent" }


                translations:
                    languages:
                        - "japanese"
                    dubbed: reject
                    subbed: reject

                series:
                    - Attack on Titan:
                        parse_only: yes
                        identified_by: ep

            subbed3:
                mock:
                    - { title: "Attack on Titan S01E01 SubFrench SubItalian 720p", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 SubEnglish 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p WEBRip", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p SubJapanese", url: "http://mock.url/file2.torrent" }
                    - { title: "Attack on Titan S01E01 720p Subbed", url: "http://mock.url/file2.torrent" }


                translations:
                    languages:
                        - "japanese"
                    dubbed: reject
                    subbed: 
                        none: reject
                        default: accept

                series:
                    - Attack on Titan:
                        parse_only: yes
                        identified_by: ep


            do_nothing_test:
                mock:
                    - {'title':'Movie1.720p.PT.ENG.TEST','url':'mock://teste1'}
                    - {'title':'Movie2.720p.Portugues.Ingles.TEST','url':'mock://teste2'}
                    - {'title':'Movie3.1080p.ENG.PT.BluRay.TEST','url':'mock://teste3'}
                translations:
                    languages_synonyms:
                        portuguese:
                            - tuga
                            - portuga
                            - portugues
                        english:
                            - ingles
                            - ing
                        spanish:
                            - espanhol
                        french:
                            - frances
                    dubbed:
                        portuguese: "do_nothing"
                        default: "reject"


            do_one_language:
                mock:
                    - {'title':'Movie1.720p.PT.ENG.TEST','url':'mock://teste1'}
                    - {'title':'Movie2.720p.Portugues.Ingles.TEST','url':'mock://teste2'}
                    - {'title':'Movie3.1080p.ENG.PT.BluRay.TEST','url':'mock://teste3'}
                translations:
                    languages_synonyms:
                        portuguese:
                            - tuga
                            - portuga
                            - portugues
                        english:
                            - ingles
                            - ing
                        spanish:
                            - espanhol
                        french:
                            - frances
                    dubbed:
                        portuguese: "accept"
                        default: "reject"
    """

    def test_force_native(self, execute_task):
        task = execute_task('dubbed1')
        assert len(task.accepted) == 2
        assert len(task.rejected) == 2
        assert len(task.undecided) == 0
        assert task.accepted[0]['title'] == 'Attack on Titan S01E01 720p WEBRip'
        assert task.accepted[1]['title'] == 'Attack on Titan S01E01 720p Japanese'

    def test_force_synonym(self, execute_task):
        task = execute_task('dubbed2')
        assert len(task.accepted) == 1
        assert len(task.rejected) == 1
        assert len(task.undecided) == 0
        assert task.accepted[0]['title'] == 'Show S01E01 Tuga 720p'

    def test_get_native(self, execute_task):
        task = execute_task('dubbed3')
        assert len(task.accepted) == 0
        assert len(task.rejected) == 2
        assert len(task.undecided) == 3
        expected = ['Movie English 720p', 'Movie 720p', 'Movie En 720p']

        assert task.undecided[0]['title'] in expected
        assert task.undecided[1]['title'] in expected
        assert task.undecided[2]['title'] in expected

        assert task.rejected[0]['title'] == 'Movie French 720p'
        assert task.rejected[1]['title'] == 'Movie Spanish 720p'

    def test_get_dubbed(self, execute_task):
        task = execute_task('dubbed_accept')
        assert len(task.accepted) == 4
        assert len(task.rejected) == 0
        assert len(task.undecided) == 1

        expected = ['Movie Dub 720p', 'Movie Dubbed 720p', 'Movie PT_BR 720p', 'Movie French 720p']

        assert task.accepted[0]['title'] in expected
        assert task.accepted[1]['title'] in expected
        assert task.accepted[2]['title'] in expected
        assert task.accepted[3]['title'] in expected

        assert task.undecided[0]['title'] == 'Movie 720p'

    def test_dont_get_dubbed(self, execute_task):
        task = execute_task('dubbed_reject')
        assert len(task.accepted) == 0
        assert len(task.rejected) == 4
        assert len(task.undecided) == 1

        expected = ['Movie Dub 720p', 'Movie Dubbed 720p', 'Movie PT_BR 720p', 'Movie French 720p']

        assert task.rejected[0]['title'] in expected
        assert task.rejected[1]['title'] in expected
        assert task.rejected[2]['title'] in expected
        assert task.rejected[3]['title'] in expected

        assert task.undecided[0]['title'] == 'Movie 720p'

    def test_subbed_language(self, execute_task):
        task = execute_task('subbed1')
        assert len(task.accepted) == 0
        assert len(task.rejected) == 4
        assert len(task.undecided) == 1

        assert task.undecided[0]['title'] == 'Attack on Titan S01E01 SubEnglish 720p WEBRip'

    def test_not_subbed(self, execute_task):
        task = execute_task('subbed2')
        assert len(task.accepted) == 0
        assert len(task.rejected) == 4
        assert len(task.undecided) == 1
        assert task.undecided[0]['title'] == 'Attack on Titan S01E01 720p WEBRip'

    def test_subbed(self, execute_task):
        task = execute_task('subbed3')
        assert len(task.accepted) == 4
        assert len(task.rejected) == 1
        assert len(task.undecided) == 0

        assert task.accepted[0]['title'] == 'Attack on Titan S01E01 SubFrench SubItalian 720p'
        assert task.accepted[1]['title'] == 'Attack on Titan S01E01 SubEnglish 720p WEBRip'
        assert task.accepted[2]['title'] == 'Attack on Titan S01E01 720p SubJapanese'
        assert task.accepted[3]['title'] == 'Attack on Titan S01E01 720p Subbed'

        assert task.rejected[0]['title'] == 'Attack on Titan S01E01 720p WEBRip'

    def test_do_nothing_test(self, execute_task):
        task = execute_task('do_nothing_test')
        assert len(task.accepted) == 0
        assert len(task.rejected) == 0
        assert len(task.undecided) == 3

    def test_do_one_language(self, execute_task):
        task = execute_task('do_one_language')
        assert len(task.accepted) == 3
        assert len(task.rejected) == 0
        assert len(task.undecided) == 0
