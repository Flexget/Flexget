import { connect } from 'react-redux';
import { GET_VERSION } from 'store/version/actions';
import Login from './Login';

export function mapStateToProps({ auth, status }) {
  return {
    redirectToReferrer: !!auth.loggedIn,
    loading: !!status.loading[GET_VERSION],
  };
}

export default connect(mapStateToProps)(Login);
export { Login };
