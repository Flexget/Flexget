import React from 'react';
import { shallow } from 'enzyme';
import History from 'components/history';

describe('components/history', () => {
  it('renders correctly', () => {
    const tree = shallow(
      <History
        getHistory={jest.fn()}
      />
    );
    expect(tree).toMatchSnapshot();
  });
});
