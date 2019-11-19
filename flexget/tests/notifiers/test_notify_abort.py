class TestNotifyAbort:
    config = """
        tasks:
          test_abort:
            # causes on_task_abort to be called
            disable: builtins

            # causes abort
            abort: yes

            notify:
              abort:
                via:
                  - debug_notification:
                      user_key: user_key
          no_crash:
            disable: builtins
            notify:
              abort:
                via:
                  - debug_notification:
                      user_key: user_key
    """

    def test_notify_abort(self, execute_task, debug_notifications):
        execute_task('test_abort', abort=True)
        data = ('Task test_abort has aborted!', 'Reason: abort plugin', {'user_key': 'user_key'})

        assert debug_notifications[0] == data
        assert len(debug_notifications) == 1

    def test_no_crash(self, execute_task, debug_notifications):
        execute_task('no_crash')
        assert len(debug_notifications) == 0
