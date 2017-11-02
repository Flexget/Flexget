import React from 'react';
import renderer from 'react-test-renderer';
import { themed } from '../../utils/tests';
import HomePage from '../Home';

describe('pages/Home', () => {
  it('renders correctly', () => {
    const tree = renderer.create(
      themed(<HomePage />),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
