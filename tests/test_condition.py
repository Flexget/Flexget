from pendulum import DateTime

from flexget.entry import Entry


class TestCondition:
    config = """
        templates:
          global:
            disable: [seen]
            mock:
              - {title: 'test', year: 2000}
              - {title: 'brilliant', rating: 9.9}
              - {title: 'fresh', year: 2011}

        tasks:
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

    def test_reject(self, execute_task):
        task = execute_task('test_condition_reject')
        count = len(task.rejected)
        assert count == 1

    def test_accept(self, execute_task):
        task = execute_task('test_condition_accept')
        count = len(task.accepted)
        assert count == 2

    def test_implicit_and(self, execute_task):
        for i in "12":
            task = execute_task('test_condition_and' + i)
            count = len(task.accepted)
            assert count == int(i)

    def test_has_field(self, execute_task):
        task = execute_task('test_has_field')
        assert len(task.accepted) == 2

    def test_sub_plugin(self, execute_task):
        task = execute_task('test_sub_plugin')
        entry = task.find_entry('accepted', title='test', some_field='some value')
        assert entry
        assert len(task.accepted) == 1


class TestQualityCondition:
    config = """
        templates:
          global:
            disable: [seen]
            mock:
              - {title: 'Smoke.1280x720'}
              - {title: 'Smoke.720p'}
              - {title: 'Smoke.1080i'}
              - {title: 'Smoke.HDTV'}
              - {title: 'Smoke.cam'}
              - {title: 'Smoke.HR'}
            accept_all: yes

        tasks:
          test_condition_quality_name_2:
            if:
              - "quality in ['hdtv', '1080i']": reject

          test_condition_quality_value_3:
            if:
              - "quality < '720p'": reject
    """

    def test_quality(self, manager, execute_task):
        for taskname in manager.config['tasks']:
            task = execute_task(taskname)
            count = len(task.rejected)
            expected = int(taskname[-1])
            assert count == expected, f"Expected {expected} rejects, got {count}"


class TestDateCondition:
    config = """
        templates:
          global:
            disable: [seen]
        tasks:
          test_now:
            if:
            - dt_field < now: accept
          test_compare:
            if:
            - dt_field1 < dt_field2: accept
    """

    def test_naive(self, execute_task):
        entry = Entry(title='1960', url='', dt_field=DateTime.create(1960, 1, 1, tz=None))
        task = execute_task('test_now', options={'inject': [entry]})
        assert len(task.accepted) == 1
        entry = Entry(title='future', url='', dt_field=DateTime.now().add(days=1).naive())
        task = execute_task('test_now', options={'inject': [entry]})
        assert len(task.accepted) == 0

    def test_tz(self, execute_task):
        # This would end up being false if a naive comparison was done, but with timezones dt1 < dt2
        dt1 = DateTime.create(2023, 1, 1, 2, tz="America/New_York")
        dt2 = DateTime.create(2023, 1, 1, 1, tz="America/Los_Angeles")
        entry = Entry(title='entry', url='', dt_field1=dt1, dt_field2=dt2)
        task = execute_task('test_compare', options={'inject': [entry]})
        assert len(task.accepted) == 1
        # Sanity check that when we reverse the comparison it's not true
        entry = Entry(title='entry', url='', dt_field1=dt2, dt_field2=dt1)
        task = execute_task('test_compare', options={'inject': [entry]})
        assert len(task.accepted) == 0
