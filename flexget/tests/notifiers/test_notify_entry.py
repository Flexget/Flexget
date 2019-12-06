class TestNotifyEntry:
    config = """
        tasks:
          test_basic_notify:
            mock:
             - {title: 'foo', url: 'http://bla.com'}
             - {title: 'bar', url: 'http://bla2.com'}
            accept_all: yes
            notify:
              entries:
                title: "{{title}}"
                message: "{{url}}"
                via:
                  - debug_notification:
                      api_key: apikey
        """

    def test_basic_notify(self, debug_notifications, execute_task):
        expected = [
            ('foo', 'http://bla.com', {'api_key': 'apikey'}),
            ('bar', 'http://bla2.com', {'api_key': 'apikey'}),
        ]
        task = execute_task('test_basic_notify')

        assert len(task.accepted) == 2
        assert debug_notifications == expected
