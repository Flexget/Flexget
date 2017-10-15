import React from 'react';
import renderer from 'react-test-renderer';
import InfoCard from 'pages/Home/InfoCard';
import { themed } from 'utils/tests';

describe('pages/Home/InfoCard', () => {
  it('renders correctly', () => {
    const tree = renderer.create(
      themed(<InfoCard />),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
