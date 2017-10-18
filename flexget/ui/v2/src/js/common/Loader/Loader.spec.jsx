import React from 'react';
import { shallow } from 'enzyme';
import Loader from 'common/Loader';

describe('common/Loader', () => {
  it('should render properly when loading', () => {
    expect(
      shallow(<Loader isLoading pastDelay />)
    ).toMatchSnapshot();
  });

  it('should render properly when timed out', () => {
    expect(
      shallow(<Loader isLoading timedOut />)
    ).toMatchSnapshot();
  });

  it('should render properly when errored', () => {
    expect(
      shallow(<Loader error />)
    ).toMatchSnapshot();
  });
});
