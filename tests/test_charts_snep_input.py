from __future__ import unicode_literals, division, absolute_import

from tests import FlexGetBase, use_vcr

class TestChartsSnepInput(FlexGetBase):
    __yaml__ = """
        tasks:
          test:
            charts_snep_input: radio
    """

    @use_vcr
    def test_input(self):
        self.execute_task('test')
        assert len(self.task.entries) == 60, 'Produces %i entries, expected 60' % len(self.task.entries)