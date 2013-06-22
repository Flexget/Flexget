from __future__ import unicode_literals, division, absolute_import

from nose.tools import raises
from datetime import datetime

from flexget.plugins.filter.regexp_queue import (queue_add,
                                        queue_del,
                                        queue_edit,
                                        queue_get_single,
                                        queue_get,
                                        queue_forget,
                                        QueuedRegexp,
                                        FilterRegexpQueue,
                                        QueueError,
                                        )
from flexget.plugins.cli.regexp_queue import RegexpQueueCLI, CLIException

from flexget.utils.database import with_session
from flexget.utils.sqlalchemy_utils import row_to_dict
from flexget.utils.qualities import Requirements as QRequirements, Quality
from flexget.manager import Session
from tests import FlexGetBase


class TestRegexpQueue(FlexGetBase):

    __yaml__ = """
        tasks:
          test_matches:
            mock:
              - {title: "Text Hello Text"}
          test_task:
            mock:
              - {title: "Text Hello Text"}
              - {title: "Text Hello Text2"}
            regexp_queue: True
    """

    def test_add_item(self):
        regexp = 'Text.*Text'

        assert queue_add(regexp=regexp).regexp == regexp, "Regexp wasn't the same"

    @raises(QueueError)
    def test_add_duplicate_item(self):
        regexp = 'Text.*Text'

        assert queue_add(regexp=regexp).regexp == regexp, "Regexp wasn't the same"
        queue_add(regexp=regexp)


    def test_add_item_with_quality(self):
        regexp = "Test.*Test"
        quality_req = QRequirements('flac')
        item = queue_add(regexp=regexp, quality=quality_req)

        assert not item is None
        assert item.quality_req.text == quality_req.text, "Quality wasn't the same"

    def test_del_item(self):
        regexp = 'Text.*Text'
        item = queue_add(regexp=regexp)

        assert queue_del(regexp=regexp) == item.regexp, 'Didn\'t delete the right item.'


    def test_get_single_item(self):
        regexp = 'Text.*Text'
        input_item = queue_add(regexp=regexp)
        output_item = queue_get_single(regexp=regexp)

        assert row_to_dict(input_item) == row_to_dict(output_item)

    @with_session
    def test_forget_item(self, session=None):
        regexp = 'Text.+ABC'

        item = queue_add(regexp=regexp, session=session)
        item.downloaded = datetime.now()

        assert not item.downloaded is None

        edited_item = queue_forget(regexp=regexp, session=session)

        assert edited_item.downloaded is None

    def test_edit_item(self):
        regexp = 'Text.*Text-123'
        new_quality = QRequirements('flac')

        item = queue_add(regexp=regexp)
        edited_item = queue_edit(regexp=regexp, quality=new_quality.text)

        d_item = row_to_dict(item)
        d_edited_item = row_to_dict(edited_item)

        # remove quality since they differ
        d_item.pop('quality'), d_edited_item.pop('quality')

        assert d_edited_item == d_item, 'Didn\'t edit the right item.'

        # TODO: quality_req doesn't implement __eq__ which would just compare self.text == b.text
        assert edited_item.quality == new_quality.text, 'Quality text should be the same.'
        assert str(edited_item.quality_req) == str(new_quality), 'str.-repr. of qualties should be same'

    def test_get_item(self):
        regexp = 'Text.*Text'
        item = queue_add(regexp=regexp)
        queue_entries = queue_get()

        assert len(queue_entries) == 1
        assert row_to_dict(queue_entries[0]) == row_to_dict(item)

    def test_matches(self):
        self.execute_task('test_matches')
        entry = self.task.entries[0]
        queue_add(regexp=entry['title'])

        regexp_filter = FilterRegexpQueue()
        assert not regexp_filter.matches(task=self.task, config=None, entry=entry) is None

    def test_matches_fail(self):
        self.execute_task('test_matches')
        entry = self.task.entries[0]
        queue_add(regexp='XXXX')

        regexp_filter = FilterRegexpQueue()
        assert regexp_filter.matches(task=self.task, config=None, entry=entry) is None

    def test_task(self):
        queue_add(regexp='2$')
        self.execute_task('test_task')

        assert self.task.find_entry('accepted', title='Text Hello Text2')
        assert len(self.task.accepted) == 1

    def test_task_fail(self):
        queue_add(regexp='XXXXXXXX')
        self.execute_task('test_task')

        assert self.task.find_entry('accepted', title='Text Hello Text') is None
        assert len(self.task.accepted) == 0



class TestRegexpQueueCLI(FlexGetBase):
    def test_register_cli(self):
        RegexpQueueCLI.register()

    def test_add_regexp(self):
        RegexpQueueCLI.handle(None, ['add','test','720p+'])
        queue_entries = queue_get()

        assert len(queue_entries) == 1

        entry = queue_entries[0]

        assert entry.regexp == 'test'
        assert entry.quality_req.text == '720p+'

    @raises(CLIException)
    def test_del_nonexisting_regexp(self):
        RegexpQueueCLI.do_del(None, ['test', '720p+'])

    def test_del_existing_regexp(self):
        RegexpQueueCLI.do_add(None, ['test2','720p'])
        RegexpQueueCLI.do_del(None, ['test2']), "Shouldn't throw exception"

    @raises(CLIException)
    def test_del_without_arg(self):
        RegexpQueueCLI.do_del(None, [])

    def test_list_empty(self):
        RegexpQueueCLI.do_list(None, [])

    def test_list_not_empty(self):
        RegexpQueueCLI.do_add(None, ['test'])
        RegexpQueueCLI.do_list(None, [])

    def test_list_downloaded_empty(self):
        RegexpQueueCLI.do_downloaded(None, [])

    def test_list_donloaded_not_empty(self):
        item = queue_add(regexp='test3')
        item.downloaded = True
        RegexpQueueCLI.do_downloaded(None, [])

    @raises(CLIException)
    def test_forget_throws(self):
        RegexpQueueCLI.do_forget(None, [])

    @raises(CLIException)
    def test_forget_throws_invalid_item(self):
        RegexpQueueCLI.do_forget(None, ['test'])

    @with_session
    def test_forget(self, session=None):
        regexp = 'test'
        item = queue_add(regexp=regexp, session=session)
        item.downloaded = datetime.now()

        assert not item.downloaded is None

        RegexpQueueCLI.do_forget(None, [regexp])
        item = queue_get_single(regexp=regexp, session=session)

        assert item.downloaded is None,\
                "Should no longer be marked as downloaded (%s)" % item.downloaded
