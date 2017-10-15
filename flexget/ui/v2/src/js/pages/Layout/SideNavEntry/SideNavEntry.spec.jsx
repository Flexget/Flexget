import React from 'react';
import renderer from 'react-test-renderer';
import SideNavEntry from 'pages/Layout/SideNavEntry';
import { themed, router } from 'utils/tests';

describe('pages/Layout/SideNavEntry', () => {
  it('renders correctly with link', () => {
    const tree = renderer.create(
      router(themed(<SideNavEntry icon="icon" label="Test" link="/test" />)),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('renders correctly without link', () => {
    const tree = renderer.create(
      themed(<SideNavEntry icon="icon" label="Test" />),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
