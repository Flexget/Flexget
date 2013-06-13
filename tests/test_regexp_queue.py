from __future__ import unicode_literals, division, absolute_import

from flexget.plugins.filter.regexp_queue import queue_add, queue_del, queue_edit, QueuedRegexp
from flexget.utils.qualities import Requirements as QRequirements, Quality
from flexget.manager import Session
from tests import FlexGetBase


class TestRegexpQueue(FlexGetBase):
    def test_add_item(self):
        regexp = 'Text.*Text'
        assert queue_add(regexp=regexp).regexp == regexp, "Regexp wasn't the same"

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

    def test_edit_item(self):
        regexp = 'Text.*Text'
        item = queue_add(regexp=regexp)
        new_quality = QRequirements('flac')
        assert queue_edit(regexp=regexp, quality=new_quality.text) == regexp, 'Didn\'t edit the right item.'
        session = Session()
        item = session.query(QueuedRegexp).filter(QueuedRegexp.regexp == regexp).first()

        # TODO: quality_req doesn't implement __eq__ which would just compare self.text == b.text
        assert item.quality == new_quality.text, 'Quality text should be the same.'
        assert str(item.quality_req) == str(new_quality), 'str.-repr. of qualties should be same'

