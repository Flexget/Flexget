import React from 'react';
import { shallow } from 'enzyme';
import LogTable from 'components/log/LogTable';
import { themed } from 'utils/tests';

describe('components/log/LogTable', () => {
  it('renders correctly', () => {
    const wrapper = shallow(
      themed(<LogTable messages={[]} />)
    );
    expect(wrapper).toMatchSnapshot();
  });
});
