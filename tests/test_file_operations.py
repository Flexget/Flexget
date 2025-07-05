from pathlib import Path


class TestDelete:
    config = """
        templates:
            global:
                accept_all: yes
        tasks:
            delete:
                delete: yes
                mock:
                  - {title: file.mkv, location: __tmp__/file.mkv}
            delete_no_location:
                delete: yes
                mock:
                  - {title: file.mkv}
            clean_source:
                delete:
                    clean_source: 1
                mock:
                  - {title: file.mkv, location: __tmp__/1/file.mkv}
            along:
                delete:
                    along:
                        extensions:
                            - srt
                        subdirs: subdir
                mock:
                  - {title: file.mkv, location: __tmp__/file.mkv}
            along_invalid_subdir:
                delete:
                    along:
                        extensions: srt
                        subdirs:
                            - subdir0
                            - file
                mock:
                  - {title: file.mkv, location: __tmp__/file.mkv}
        """

    def test_delete(self, execute_task, tmp_path):
        (tmp_path / 'file.mkv').touch()
        assert (tmp_path / 'file.mkv').exists()
        execute_task('delete')
        assert not (tmp_path / 'file.mkv').exists()

    def test_delete_test_mode(self, execute_task, tmp_path):
        (tmp_path / 'file.mkv').touch()
        assert (tmp_path / 'file.mkv').exists()
        execute_task('delete', options={'test': True})

    def test_delete_no_location(self, execute_task, tmp_path):
        execute_task('delete_no_location')

    def test_clean_source(self, execute_task, tmp_path):
        (tmp_path / '1').mkdir()
        (tmp_path / '1' / 'file.mkv').touch()
        assert (tmp_path / '1' / 'file.mkv').exists()
        (tmp_path / '1' / 'file0.mkv').touch()
        execute_task('clean_source')
        assert not (tmp_path / '1').exists()

    def test_clean_source_test_mode(self, execute_task, tmp_path):
        (tmp_path / '1').mkdir()
        (tmp_path / '1' / 'file.mkv').touch()
        assert (tmp_path / '1' / 'file.mkv').exists()
        (tmp_path / '1' / 'file0.mkv').touch()
        execute_task('clean_source', options={'test': True})

    def test_along(self, execute_task, tmp_path):
        (tmp_path / 'file.mkv').touch()
        (tmp_path / 'file.srt').touch()
        (tmp_path / 'subdir').mkdir()
        (tmp_path / 'subdir' / 'file.srt').touch()
        assert (tmp_path / 'file.srt').exists()
        assert (tmp_path / 'subdir' / 'file.srt').exists()
        execute_task('along')
        assert not (tmp_path / 'file.srt').exists()
        assert not (tmp_path / 'subdir' / 'file.srt').exists()
        execute_task('along', options={'test': True})

    def test_along_invalid_subdir(self, execute_task, tmp_path):
        (tmp_path / 'file.mkv').touch()
        (tmp_path / 'file.srt').touch()
        (tmp_path / 'file').touch()
        assert (tmp_path / 'file.srt').exists()
        execute_task('along_invalid_subdir')
        assert not (tmp_path / 'file.srt').exists()
        execute_task('along_invalid_subdir', options={'test': True})


class TestCopy:
    config = f"""
            templates:
                global:
                    accept_all: yes
            tasks:
                copy:
                    copy:
                      rename: a.b.c
                      to: __tmp__
                    mock:
                      - {{title: file.mkv, location: {Path(__file__).parent}/file_operation_test_dir/file.mkv}}
            """

    def test_copy(self, execute_task, tmp_path):
        execute_task('copy')
        assert (tmp_path / 'a.b.c.mkv').exists()
        execute_task('copy', options={'test': True})


class TestMove:
    config = """
            templates:
                global:
                    accept_all: yes
            tasks:
                move:
                    move:
                      rename: a.b.c
                      to: __tmp__/to
                    mock:
                      - {title: file.mkv, location: __tmp__/file.mkv}
            """

    def test_move(self, execute_task, tmp_path):
        (tmp_path / 'file.mkv').touch()
        execute_task('move')
        assert (tmp_path / 'to' / 'a.b.c.mkv').exists()

    def test_move_test_mode(self, execute_task, tmp_path):
        (tmp_path / 'file.mkv').touch()
        execute_task('move', options={'test': True})
