import React from 'react';
import { shallow } from 'enzyme';
import LoadingBar from 'components/common/LoadingBar';

describe('components/common/LoadingBar', () => {
  it('should render properly when loading', () => {
    expect(
      shallow(<LoadingBar loading />)
    ).toMatchSnapshot();
  });

  it('should render properly when not loading', () => {
    expect(
      shallow(<LoadingBar />)
    ).toMatchSnapshot();
  });
});
