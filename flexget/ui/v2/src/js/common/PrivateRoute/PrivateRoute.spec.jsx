import React from 'react';
import { mapStateToProps, PrivateRoute } from 'common/PrivateRoute';
import renderer from 'react-test-renderer';
import { router } from 'utils/tests';

const Component = () => <div />;

describe('common/PrivateRoute', () => {
  describe('PrivateRoute', () => {
    it('renders correctly when logged in', () => {
      const tree = renderer.create(
        router(<PrivateRoute component={Component} loggedIn />)
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    xit('renders correctly when logged out', () => {
      const tree = renderer.create(
        router(<PrivateRoute component={Component} loggedIn={false} />)
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });
  });

  describe('mapStateToProps', () => {
    it('should return logged in if logged in', () => {
      expect(mapStateToProps({ auth: { loggedIn: true } })).toMatchSnapshot();
    });

    it('should return not logged in if logged out', () => {
      expect(mapStateToProps({ auth: { } })).toMatchSnapshot();
    });
  });
});
