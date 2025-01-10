class TestArchiveFilter:
    config = """
        tasks:
            test_archives:
                filesystem:
                    path: archives/
                archives: yes
            test_no_location:
                mock:
                    - {title: 'no_location'}
                archives: yes
    """

    def test_rar(self, execute_task):
        """Test RAR acceptance"""
        task = execute_task('test_archives')
        assert task.find_entry('accepted', title='test_rar'), (
            'test_rar.rar should have been accepted'
        )

    def test_zip(self, execute_task):
        """Test Zip acceptance"""
        task = execute_task('test_archives')
        assert task.find_entry('accepted', title='test_zip'), (
            'test_zip.zip should have been accepted'
        )

    def test_invalid(self, execute_task):
        """Test non-archive rejection"""
        task = execute_task('test_archives')
        assert task.find_entry('rejected', title='invalid'), (
            'invalid.zip should have been rejected'
        )

    def test_no_location(self, execute_task):
        """Test rejection of entries with no location"""
        task = execute_task('test_no_location')
        assert task.find_entry('rejected', title='no_location'), (
            'no_location should have been rejected'
        )
