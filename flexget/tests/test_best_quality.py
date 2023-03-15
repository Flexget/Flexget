class TestBestQuality:
    config = """
        tasks:
          best_accept:
            best_quality:
              on_best: accept
            mock:
              - {title: 'Movie.720p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
              - {title: 'Movie.1080p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
          best_do_nothing:
            best_quality:
              on_best: do_nothing
            mock:
              - {title: 'Movie.720p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
              - {title: 'Movie.1080p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
          lower_do_nothing:
            best_quality:
              on_lower: do_nothing
            mock:
              - {title: 'Movie.720p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
              - {title: 'Movie.1080p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
    """

    def test_best_accept(self, execute_task):
        task = execute_task('best_accept')
        entry = task.find_entry('accepted', title='Movie.1080p.WEB-DL.X264.AC3-GRP1')
        assert entry, 'Movie.1080p.WEB-DL.X264.AC3-GRP1 should be accepted'
        entry = task.find_entry('rejected', title='Movie.720p.WEB-DL.X264.AC3-GRP1')
        assert entry, 'Movie.720p.WEB-DL.X264.AC3-GRP1 should be rejected'

    def test_best_do_nothing(self, execute_task):
        task = execute_task('best_do_nothing')
        entry = task.find_entry('undecided', title='Movie.1080p.WEB-DL.X264.AC3-GRP1')
        assert entry, 'Movie.1080p.WEB-DL.X264.AC3-GRP1 should be undecided'
        entry = task.find_entry('rejected', title='Movie.720p.WEB-DL.X264.AC3-GRP1')
        assert entry, 'Movie.720p.WEB-DL.X264.AC3-GRP1 should be rejected'

    def test_lower_do_nothing(self, execute_task):
        task = execute_task('lower_do_nothing')
        entry = task.find_entry('undecided', title='Movie.1080p.WEB-DL.X264.AC3-GRP1')
        assert entry, 'Movie.1080p.WEB-DL.X264.AC3-GRP1 should be undecided'
        entry = task.find_entry('undecided', title='Movie.720p.WEB-DL.X264.AC3-GRP1')
        assert entry, 'Movie.720p.WEB-DL.X264.AC3-GRP1 should be undecided'
