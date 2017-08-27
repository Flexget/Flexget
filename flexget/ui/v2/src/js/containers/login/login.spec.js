import { mapStateToProps } from 'containers/login';

describe('containers/login', () => {
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
