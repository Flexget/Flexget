import { getGroupedHistory } from 'store/history/selectors';

describe('store/history/selectors', () => {
  describe('getGroupedHistory', () => {
    const items = [{
      time: '2017-09-10T00:21:33',
      task: 'task1',
    }, {
      time: '2017-09-10T12:21:33',
      task: 'task2',
    }, {
      time: '2017-08-10T00:21:33',
      task: 'task1',
    }];

    it('should group properly based on time', () => {
      expect(getGroupedHistory({ items }, 'time')).toEqual({
        '2017-09-10': [items[0], items[1]],
        '2017-08-10': [items[2]],
      });
    });

    it('should group properly based on task', () => {
      expect(getGroupedHistory({ items }, 'task')).toEqual({
        task1: [items[0], items[2]],
        task2: [items[1]],
      });
    });
  });
});
