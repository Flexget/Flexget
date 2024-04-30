from pathlib import Path


class TestFilesystem:
    base = "filesystem_test_dir/"
    test1 = base + '/Test1'
    test2 = base + '/Test2'
    test3 = base + '/Test3'

    config = rf"""
        tasks:
          string:
            filesystem: {test1}
          list:
            filesystem:
              - {test1}
              - {test2}
          object_string:
            filesystem:
              path: {test1}
          object_list:
            filesystem:
              path:
                - {test1}
                - {test2}
          file_mask:
            filesystem:
              path: {test1}
              mask: '*.mkv'
          regexp_test:
            filesystem:
              path: {test1}
              regexp: '.*\.(mkv)$'
          recursive_true:
            filesystem:
              path: {test1}
              recursive: yes
          recursive_2_levels:
            filesystem:
              path: {test1}
              recursive: 2
          retrieve_files:
            filesystem:
              path: {test1}
              retrieve: files
          retrieve_files_and_dirs:
            filesystem:
              path: {test1}
              retrieve:
                - files
                - dirs
          combine_1:
            filesystem:
              path: {test1}
              mask: '*.mkv'
              recursive: 2
          combine_2:
            filesystem:
              path: {test1}
              recursive: yes
              retrieve: dirs
          non_ascii:
            filesystem:
              path: {test3}
              recursive: yes
              retrieve: [files, dirs]
        """

    item_list = [
        'file1.mkv',
        'file2.txt',
        'file10.mkv',
        'file11.txt',
        'file4.avi',
        'file3.xlsx',
        'file5.mkv',
        'dir1',
        'dir2',
        'dir4',
        'dir6',
        'dir7',
        'dir8',
    ]

    @staticmethod
    def assert_check(task, task_name, test_type, filenames):
        for file in filenames:
            file = Path(file)
            if test_type == 'positive':
                assertion_error = f'Failed {test_type} {task_name} test, did not find {file}'
                assert task.find_entry(title=file.stem), assertion_error
            else:
                assertion_error = f'Failed {test_type} {task_name} test, found {file}'
                assert not task.find_entry(title=file.stem), assertion_error

    def test_string(self, execute_task):
        task_name = 'string'
        should_exist = 'dir1', 'dir2', 'file1.mkv', 'file2.txt'
        should_not_exist = [item for item in self.item_list if item not in should_exist]
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
        self.assert_check(task, task_name, 'negative', should_not_exist)

    def test_list(self, execute_task):
        task_name = 'list'
        should_exist = ['dir1', 'dir2', 'file1.mkv', 'file2.txt', 'file10.mkv']
        should_not_exist = [item for item in self.item_list if item not in should_exist]
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
        self.assert_check(task, task_name, 'negative', should_not_exist)

    def test_object_string(self, execute_task):
        task_name = 'object_string'
        should_exist = ['dir1', 'dir2', 'file1.mkv', 'file2.txt']
        should_not_exist = [item for item in self.item_list if item not in should_exist]
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
        self.assert_check(task, task_name, 'negative', should_not_exist)

    def test_object_list(self, execute_task):
        task_name = 'object_list'
        should_exist = ['dir1', 'dir2', 'file1.mkv', 'file2.txt', 'file10.mkv']
        should_not_exist = [item for item in self.item_list if item not in should_exist]
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
        self.assert_check(task, task_name, 'negative', should_not_exist)

    def test_file_mask(self, execute_task):
        task_name = 'file_mask'
        should_exist = ['file1.mkv']
        should_not_exist = [item for item in self.item_list if item not in should_exist]
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
        self.assert_check(task, task_name, 'negative', should_not_exist)

    def test_regexp_test(self, execute_task):
        task_name = 'regexp_test'
        should_exist = ['file1.mkv']
        should_not_exist = [item for item in self.item_list if item not in should_exist]
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
        self.assert_check(task, task_name, 'negative', should_not_exist)

    def test_recursive_true(self, execute_task):
        task_name = 'recursive_true'
        should_exist = [
            'dir1',
            'dir4',
            'dir6',
            'dir7',
            'dir8',
            'file11.txt',
            'file4.avi',
            'file3.xlsx',
            'dir2',
            'file5.mkv',
            'file1.mkv',
            'file2.txt',
        ]
        should_not_exist = [item for item in self.item_list if item not in should_exist]
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
        self.assert_check(task, task_name, 'negative', should_not_exist)

    def test_recursive_2_levels(self, execute_task):
        task_name = 'recursive_2_levels'
        should_exist = [
            'dir1',
            'dir4',
            'file3.xlsx',
            'dir2',
            'file5.mkv',
            'file1.mkv',
            'file2.txt',
        ]
        should_not_exist = [item for item in self.item_list if item not in should_exist]
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
        self.assert_check(task, task_name, 'negative', should_not_exist)

    def test_retrieve_files(self, execute_task):
        task_name = 'retrieve_files'
        should_exist = ['file1.mkv', 'file2.txt']
        should_not_exist = [item for item in self.item_list if item not in should_exist]
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
        self.assert_check(task, task_name, 'negative', should_not_exist)

    def test_retrieve_files_and_dirs(self, execute_task):
        task_name = 'retrieve_files_and_dirs'
        should_exist = ['dir1', 'dir2', 'file1.mkv', 'file2.txt']
        should_not_exist = [item for item in self.item_list if item not in should_exist]
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
        self.assert_check(task, task_name, 'negative', should_not_exist)

    def test_combine_1(self, execute_task):
        task_name = 'combine_1'
        should_exist = ['file5.mkv', 'file1.mkv']
        should_not_exist = [item for item in self.item_list if item not in should_exist]
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
        self.assert_check(task, task_name, 'negative', should_not_exist)

    def test_combine_2(self, execute_task):
        task_name = 'combine_2'
        should_exist = ['dir1', 'dir4', 'dir2', 'dir6', 'dir7', 'dir8']
        should_not_exist = [item for item in self.item_list if item not in should_exist]
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
        self.assert_check(task, task_name, 'negative', should_not_exist)

    def test_non_ascii(self, execute_task):
        task_name = 'non_ascii'
        should_exist = ['\u0161 dir', '\u0152 file.txt']
        task = execute_task(task_name)

        self.assert_check(task, task_name, 'positive', should_exist)
