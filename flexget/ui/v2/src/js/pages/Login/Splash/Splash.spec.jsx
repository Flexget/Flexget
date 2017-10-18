import React from 'react';
import renderer from 'react-test-renderer';
import SplashScreen from 'pages/Login/Splash';
import { themed } from 'utils/tests';

describe('pages/splash', () => {
  it('renders correctly', () => {
    const tree = renderer.create(
      themed(<SplashScreen />),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
