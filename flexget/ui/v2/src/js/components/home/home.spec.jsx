import React from 'react';
import renderer from 'react-test-renderer';
import HomePage from 'components/home';
import { themed } from 'utils/tests';

describe('components/home', () => {
  it('renders correctly', () => {
    const tree = renderer.create(
      themed(<HomePage />),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
