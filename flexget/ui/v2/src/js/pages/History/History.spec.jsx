import React from 'react';
import { shallow } from 'enzyme';
import { History } from 'pages/History';

describe('pages/History', () => {
  it('renders correctly', () => {
    const tree = shallow(
      <History
        getHistory={jest.fn()}
      />
    );
    expect(tree).toMatchSnapshot();
  });
});
