import React from 'react';
import PrivateRoute from 'components/common/PrivateRoute';
import renderer from 'react-test-renderer';
import { router } from 'utils/tests';

const Component = () => <div />;
describe('components/common/PrivateRoute', () => {
  it('renders correctly when logged in', () => {
    const tree = renderer.create(
      router(<PrivateRoute component={Component} loggedIn />)
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('renders correctly when logged out', () => {
    const tree = renderer.create(
      router(<PrivateRoute component={Component} loggedIn={false} />)
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
