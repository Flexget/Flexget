import React from 'react';
import renderer from 'react-test-renderer';
import SideNav from 'pages/Layout/SideNav';
import { provider, themed, router } from 'utils/tests';
import fetchMock from 'fetch-mock';

describe('pages/Layout/Sidenav', () => {
  beforeEach(() => {
    fetchMock
      .get('/api/server/version', {});
  });

  xit('renders correctly with sideBarOpen', () => {
    const tree = renderer.create(
      provider(router(themed(<SideNav sideBarOpen />)), { version: {} }),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  xit('adds mini classes without sideBarOpen', () => {
    const tree = renderer.create(
      provider(router(themed(<SideNav sideBarOpen={false} />)), { version: {} }),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
