import pytest


@pytest.mark.require_optional_deps
@pytest.mark.online
class TestTelegramNotifier:
    config = """
        templates:
            global:
                mock:
                  - {title: title}
                accept_all: yes
        tasks:
            chat-id:
              notify:
                entries:
                  message: message
                  via:
                    - telegram:
                        bot_token: 7617087239:AAGUy118YHbBvGNwkDo4CDehF4gFgXq2ZqE
                        recipients:
                          - chat_id: 1394032416
            send-image-as-photo:
              notify:
                entries:
                  message: message
                  via:
                    - telegram:
                        bot_token: 7617087239:AAGUy118YHbBvGNwkDo4CDehF4gFgXq2ZqE
                        recipients:
                          - chat_id: 1394032416
                        images:
                        - photo.png
            send-image-as-document:
              notify:
                entries:
                  message: message
                  via:
                    - telegram:
                        bot_token: 7617087239:AAGUy118YHbBvGNwkDo4CDehF4gFgXq2ZqE
                        recipients:
                          - chat_id: 1394032416
                        images:
                        - document.jpg
            chat-migrated:
              notify:
                entries:
                  message: message
                  via:
                    - telegram:
                        bot_token: 7617087239:AAGUy118YHbBvGNwkDo4CDehF4gFgXq2ZqE
                        recipients:
                          - chat_id: -4882300333
        """

    def test_chat_id(self, execute_task):
        execute_task('chat-id', options={'test': True})

    def test_send_image_as_photo(self, execute_task):
        execute_task('send-image-as-photo', options={'test': True})

    def test_send_image_as_document(self, execute_task):
        execute_task('send-image-as-document', options={'test': True})

    def test_chat_migrated(self, execute_task):
        execute_task('chat-migrated', options={'test': True})
