import { mapStateToProps } from 'containers/common/PrivateRoute';

describe('containers/common/PrivateRoute', () => {
  it('should return logged in if logged in', () => {
    expect(mapStateToProps({ auth: { loggedIn: true } })).toMatchSnapshot();
  });

  it('should return not logged in if logged out', () => {
    expect(mapStateToProps({ auth: { } })).toMatchSnapshot();
  });
});
