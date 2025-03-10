class TestNotifyTask:
    config = """
        tasks:
          test_accepted:
            mock:
            - title: an entry
            - title: another entry
            accept_all: yes
            notify:
              task:
                via:
                  - debug_notification:
                      a: b
          test_nothing:
            mock:
            - title: an entry
            notify:
              task:
                via:
                  - debug_notification:
                      a: b
          test_jinja:
            mock:
            - title: entry 1
            - title: entry 2
            accept_all: yes
            notify:
              task:
                title: "{{task.name}} aoeu"
                via:
                  - debug_notification:
                      setting: 1{{task.name}}
    """

    def test_notify_accepted(self, execute_task, debug_notifications):
        execute_task('test_accepted')

        assert len(debug_notifications) == 1

    def test_no_notification(self, execute_task, debug_notifications):
        # With no accepted entries, nothing should have been sent
        execute_task('test_nothing')
        assert len(debug_notifications) == 0

    def test_jinja(self, execute_task, debug_notifications):
        execute_task('test_jinja')
        assert len(debug_notifications) == 1
        assert debug_notifications[0][0] == 'test_jinja aoeu'
        assert debug_notifications[0][2]['setting'] == '1test_jinja'
