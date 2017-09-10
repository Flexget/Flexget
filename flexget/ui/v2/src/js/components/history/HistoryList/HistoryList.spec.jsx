import React from 'react';
import { shallow } from 'enzyme';
import HistoryList from 'components/history/HistoryList';

describe('components/history/HistoryList', () => {
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
