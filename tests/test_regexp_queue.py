from __future__ import unicode_literals, division, absolute_import

from flexget.plugins.filter.regexp_queue import queue_add, queue_del, queue_edit, QueuedRegexp
from flexget.utils.qualities import Requirements as QRequirements, Quality
from flexget.manager import Session
from tests import FlexGetBase


class TestRegexpQueue(FlexGetBase):
    def test_add_item(self):
        regexp = 'Text.*Text'
        assert queue_add(regexp=regexp).get('regexp') == regexp, "Regexp wasn't the same"

    def test_add_item_with_quality(self):
        regexp = "Test.*Test"

        quality = Quality('flac')
        assert queue_add(regexp=regexp, quality=quality).get('quality') == quality.text, "Quality wasn't the same"

    def test_del_item(self):
        regexp = 'Text.*Text'
        obj_dict = queue_add(regexp=regexp)
        assert queue_del(regexp=regexp) == obj_dict['regexp'], 'Didn\'t delete the right item.'

    def test_edit_item(self):
        regexp = 'Text.*Text'
        obj_dict = queue_add(regexp=regexp)
        new_quality = QRequirements('flac')
        assert queue_edit(regexp=regexp, quality=new_quality.text) == regexp, 'Didn\'t edit the right item.'
        session = Session()
        item = session.query(QueuedRegexp).filter(QueuedRegexp.regexp == regexp).first()

        # TODO: quality_req doesn't implement __eq__ which would just compare self.text == b.text
        assert item.quality == new_quality.text, 'Quality text should be the same.'
        assert str(item.quality_req) == str(new_quality), 'str.-repr. of qualties should be same'

