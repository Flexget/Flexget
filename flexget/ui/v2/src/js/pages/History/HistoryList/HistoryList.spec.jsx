import React from 'react';
import { shallow } from 'enzyme';
import { mapStateToProps, HistoryList } from 'pages/History/HistoryList';

describe('pages/History/HistoryList', () => {
  describe('HistoryList', () => {
    it('renders correctly', () => {
      const tree = shallow(
        <HistoryList
          getHistory={jest.fn()}
          history={{
            '2017-09-09': [{
              task: 'task',
              id: 1,
              title: 'something',
            }],
          }}
          grouping="time"
          hasMore
        />
      );
      expect(tree).toMatchSnapshot();
    });
  });

  describe('mapStateToProps', () => {
    it('should return the right params if there are more', () => {
      const result = mapStateToProps({
        history: {
          items: [{ task: 'task_name' }],
          totalCount: 3,
        },
      }, {
        grouping: 'task',
      });

      expect(result.history).toMatchSnapshot();
      expect(result.hasMore).toBe(true);
    });

    it('should return the right params if there are not more', () => {
      const result = mapStateToProps({
        history: {
          items: [{ task: 'task_name' }],
          totalCount: 1,
        },
      }, {
        grouping: 'task',
      });

      expect(result.history).toMatchSnapshot();
      expect(result.hasMore).toBe(false);
    });
  });
});
