from __future__ import unicode_literals, division, absolute_import

from tests import FlexGetBase, use_vcr


class TestChartsSnepInput(FlexGetBase):
    __yaml__ = """
        tasks:
          test:
            charts_snep_input: radio
          bad source:
            charts_snep_input: club
    """

    @use_vcr
    def test_input(self):
        self.execute_task('test')
        assert len(self.task.entries) == 60, 'Produces %i entries, expected 60' % len(self.task.entries)

    def test_source(self):
        self.execute_task('bad source')
        assert len(self.task.entries) == 0, 'Produces %i entries, expected 0' % len(self.task.entries)