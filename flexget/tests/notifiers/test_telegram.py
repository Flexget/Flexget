import pytest


@pytest.mark.extras
@pytest.mark.online
class TestTelegramNotifier:
    config = """
      tasks:
        tg:
          mock:
            - title: an entry
          accept_all: yes
          notify:
            task:
              message: Notification body
              via:
                - telegram:
                    bot_token: 7617087239:AAGUy118YHbBvGNwkDo4CDehF4gFgXq2ZqE
                    recipients:
                      - chat_id: 1394032416
    """

    def test_chat_id(self, execute_task):
        execute_task('tg')
