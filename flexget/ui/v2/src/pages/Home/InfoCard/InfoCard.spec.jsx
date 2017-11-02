import React from 'react';
import renderer from 'react-test-renderer';
import { themed } from '../../../utils/tests';
import InfoCard from '../InfoCard';

describe('pages/Home/InfoCard', () => {
  it('renders correctly', () => {
    const tree = renderer.create(
      themed(<InfoCard />),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
