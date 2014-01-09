from __future__ import unicode_literals, division, absolute_import

from flexget.manager import Session
from flexget.utils.simple_persistence import SimplePersistence
from tests import FlexGetBase


class TestSimplePersistence(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'irrelevant'}
    """

    def test_setdefault(self):
        self.execute_task('test')

        task = self.task

        value1 = task.simple_persistence.setdefault('test', 'abc')
        value2 = task.simple_persistence.setdefault('test', 'def')

        assert value1 == value2, 'set default broken'

    def test_nosession(self):
        persist = SimplePersistence('testplugin')
        persist['aoeu'] = 'test'
        assert persist['aoeu'] == 'test'
        # Make sure it commits and actually persists
        persist = SimplePersistence('testplugin')
        assert persist['aoeu'] == 'test'

    def test_withsession(self):
        session = Session()
        persist = SimplePersistence('testplugin', session=session)
        persist['aoeu'] = 'test'
        assert persist['aoeu'] == 'test'
        # Make sure it didn't commit or close our session
        session.rollback()
        assert 'aoeu' not in persist
