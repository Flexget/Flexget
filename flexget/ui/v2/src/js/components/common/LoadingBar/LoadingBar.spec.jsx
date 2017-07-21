import React from 'react';
import renderer from 'react-test-renderer';
import LoadingBar from 'components/common/LoadingBar';
import { themed } from 'utils/tests';

describe('components/common/LoadingBar', () => {
  it('should render properly when loading', () => {
    expect(
      renderer.create(themed(<LoadingBar loading />))
    ).toMatchSnapshot();
  });

  it('should render properly when not loading', () => {
    expect(
      renderer.create(themed(<LoadingBar loading />))
    ).toMatchSnapshot();
  });
});
