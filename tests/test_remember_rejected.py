from __future__ import unicode_literals, division, absolute_import

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import parse_timedelta
from tests import FlexGetBase


class RejectRememberPlugin(object):
    def on_task_filter(self, task, config):
        for entry in task.all_entries:
            if isinstance(config, basestring):
                entry.reject(remember_time=parse_timedelta(config))
            else:
                entry.reject(remember=True)


@event('plugin.register')
def register_plugin():
    plugin.register(RejectRememberPlugin, 'test_remember_reject', api_ver=2, debug=True)


class TestRememberRejected(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'title 1', url: 'http://localhost/title1'}
            test_remember_reject: yes
    """

    def test_remember_rejected(self):
        self.execute_task('test')
        assert self.task.find_entry('rejected', title='title 1', rejected_by='test_remember_reject')
        self.execute_task('test')
        assert self.task.find_entry('rejected', title='title 1', rejected_by='remember_rejected'),\
            'remember_rejected should have rejected'
