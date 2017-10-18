import React from 'react';
import renderer from 'react-test-renderer';
import { themed, router } from 'utils/tests';
import Logo from 'pages/Layout/Logo';

describe('pages/Layout/Logo', () => {
  it('renders correctly with sideBarOpen', () => {
    const tree = renderer.create(
      router(themed(<Logo sideBarOpen />)),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('adds logoMini class without sideBarOpen', () => {
    const tree = renderer.create(
      router(themed(<Logo sideBarOpen={false} />)),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
