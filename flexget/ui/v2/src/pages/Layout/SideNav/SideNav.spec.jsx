import React from 'react';
import fetchMock from 'fetch-mock';
import renderer from 'react-test-renderer';
import SideNav from '../SideNav';
import { provider, themed, router } from '../../../utils/tests';

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
