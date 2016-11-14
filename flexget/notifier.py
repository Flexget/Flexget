from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin


class Notifier(object):
    def __init__(self, task, scope, iterate_on, test):
        self.task = task
        self.scope = scope
        if scope == 'entries':
            self.iterate_on = iterate_on
        elif scope == 'task':
            self.iterate_on = [task]
        self.test = test

    def notify(self):
        raise NotImplementedError
