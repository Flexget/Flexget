import React from 'react';
import renderer from 'react-test-renderer';
import InfoCard from 'components/home/InfoCard';
import { themed } from 'utils/tests';

describe('components/home/InfoCard', () => {
  it('renders correctly', () => {
    const tree = renderer.create(
      themed(<InfoCard />),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
