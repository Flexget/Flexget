from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase

#todo: merge into test_series

def age_series(**kwargs):
    from flexget.plugins.filter.series import Release
    from flexget.manager import Session
    import datetime
    session = Session()
    session.query(Release).update({'first_seen': datetime.datetime.now() - datetime.timedelta(**kwargs)})
    session.commit()

class TestImportSeries(FlexGetBase):

    __yaml__ = """
        tasks:
          test_import_altnames:
            configure_series:
              from:
                mock:
                  - {title: 'the show', alternate_name: 'le show'}
            mock:
              - title: le show s03e03
    """

    def test_timeframe_max(self):
        """Tests configure_series as well as timeframe with max_quality."""
        self.execute_task('test_import_altnames')
        entry = self.task.find_entry(title='le show s03e03')
        assert entry.accepted, 'entry matching series alternate name should have been accepted.'
        assert entry['series_name'] == 'the show', 'entry series should be set to the main name'
