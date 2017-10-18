import React from 'react';
import { Login, mapStateToProps } from 'pages/Login';
import renderer from 'react-test-renderer';
import { provider, router, themed } from 'utils/tests';

const Component = () => <div />;
describe('pages/Login', () => {
  describe('Login', () => {
    it('renders correctly when logged in', () => {
      const tree = renderer.create(
        router(themed(<Login
          component={Component}
          redirectToReferrer
          location={{}}
        />))
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });

    it('renders correctly when logged out', () => {
      const tree = renderer.create(
        provider(router(themed(<Login
          component={Component}
          redirectToReferrer={false}
          location={{}}
        />)), { status: {} })
      ).toJSON();
      expect(tree).toMatchSnapshot();
    });
  });

  describe('mapStateToProps', () => {
    it('should return logged in if logged in', () => {
      expect(mapStateToProps({
        auth: { loggedIn: true },
        status: { loading: {} },
      })).toMatchSnapshot();
    });

    it('should return not logged in if logged out', () => {
      expect(mapStateToProps({ auth: { }, status: { loading: {} } })).toMatchSnapshot();
    });
  });
});
