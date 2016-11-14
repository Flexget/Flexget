from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin


class Notifier(object):
    def __init__(self, task, scope, iterate_on, test, plugin_config):
        """
        A base class to be used by notifier plugins, enable iterating different elements (such as accepted or rejected
         entries
        :param task: The task instance
        :param scope: Notification scope, can be either "entries" or "task"
        :param iterate_on: The entry container to iterate on (such as task.accepted). If scope is "task" it is unneeded.
        :param test: Test mode, task.options.test
        :param plugin_config: The notifier plugin config
        """
        self.task = task
        self.scope = scope
        if scope == 'entries':
            self.iterate_on = iterate_on
        elif scope == 'task':
            self.iterate_on = [[task]]
        else:
            raise ValueError('scope must be \'entries\' or \'task\'')
        self.test = test
        self.config = plugin_config

    def notify(self):
        """
        Override this method to send the notification
        """
        raise NotImplementedError
