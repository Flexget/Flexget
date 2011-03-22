from tests import FlexGetBase


class TestCondition(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            disable_builtins: [seen]
            mock:
              - {title: 'test', year: 2000}
              - {title: 'brilliant', rating: 9.9}
              - {title: 'fresh', year: 2011}

        feeds:
          test_condition_reject:
            if:
              - year < 2011: reject

          test_condition_accept:
            if:
              - year>=2010: accept
              - rating>9: accept

          test_condition_and1:
            if:
              - "'t' in title and rating>9": accept
          test_condition_and2:
            if:
              - "'t' in title": accept

          test_has_field:
            if:
              - has_field('year'): accept

          test_sub_plugin:
            if:
              - title.upper() == 'TEST':
                  set:
                    some_field: some value
                  accept_all: yes
    """

    def test_reject(self):
        self.execute_feed('test_condition_reject')
        count = len(self.feed.rejected)
        assert count == 1

    def test_accept(self):
        self.execute_feed('test_condition_accept')
        count = len(self.feed.accepted)
        assert count == 2

    def test_implicit_and(self):
        for i in "12":
            self.execute_feed('test_condition_and' + i)
            count = len(self.feed.accepted)
            assert count == int(i)

    def test_has_field(self):
        self.execute_feed('test_has_field')
        assert len(self.feed.accepted) == 2

    def test_sub_plugin(self):
        self.execute_feed('test_sub_plugin')
        entry = self.feed.find_entry('accepted', title='test', some_field='some value')
        assert entry
        assert len(self.feed.accepted) == 1


class TestQualityCondition(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            disable_builtins: [seen]
            mock:
              - {title: 'Smoke.1280x720'}
              - {title: 'Smoke.720p'}
              - {title: 'Smoke.1080i'}
              - {title: 'Smoke.HDTV'}
              - {title: 'Smoke.cam'}
              - {title: 'Smoke.HR'}
            accept_all: yes

        feeds:
          test_condition_quality_name_2:
            if:
              - "quality in ['hdtv', '1080i']": reject

          test_condition_quality_value_3:
            if:
              - "quality < '720p'": reject
    """

    def test_quality(self):
        for feedname in self.manager.config['feeds']:
            self.execute_feed(feedname)
            count = len(self.feed.rejected)
            expected = int(feedname[-1])
            assert count == expected, "Expected %s rejects, got %d" % (expected, count)
