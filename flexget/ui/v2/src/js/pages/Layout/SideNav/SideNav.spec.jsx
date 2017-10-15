import React from 'react';
import renderer from 'react-test-renderer';
import Sidenav from 'pages/Layout/Sidenav';
import { provider, themed, router } from 'utils/tests';
import fetchMock from 'fetch-mock';

describe('pages/Layout/Sidenav', () => {
  beforeEach(() => {
    fetchMock
      .get('/api/server/version', {});
  });

  it('renders correctly with sideBarOpen', () => {
    const tree = renderer.create(
      provider(router(themed(<Sidenav sideBarOpen />)), { version: {} }),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('adds mini classes without sideBarOpen', () => {
    const tree = renderer.create(
      provider(router(themed(<Sidenav sideBarOpen={false} />)), { version: {} }),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
