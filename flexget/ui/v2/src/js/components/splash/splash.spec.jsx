import React from 'react';
import renderer from 'react-test-renderer';
import SplashScreen from 'components/splash';
import { themed } from 'utils/tests';

describe('components/splash', () => {
  it('renders correctly', () => {
    const tree = renderer.create(
      themed(<SplashScreen />),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
