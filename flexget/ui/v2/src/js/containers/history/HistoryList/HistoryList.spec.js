import { mapStateToProps } from 'containers/history/HistoryList';

describe('containers/history/HistoryList', () => {
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
