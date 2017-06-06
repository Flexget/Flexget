import React from 'react';
import renderer from 'react-test-renderer';
import Sidenav from 'components/layout/Sidenav';
import { themed, router } from 'utils/tests';

describe('components/layout/Sidenav', () => {
  it('renders correctly with sideBarOpen', () => {
    const tree = renderer.create(
      router(themed(<Sidenav sideBarOpen />)),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('adds mini classes without sideBarOpen', () => {
    const tree = renderer.create(
      router(themed(<Sidenav sideBarOpen={false} />)),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
