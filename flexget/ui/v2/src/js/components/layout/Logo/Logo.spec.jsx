import React from 'react';
import renderer from 'react-test-renderer';
import Logo from 'components/layout/Logo';
import { themed, router } from 'utils/tests';

describe('components/layout/Logo', () => {
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
