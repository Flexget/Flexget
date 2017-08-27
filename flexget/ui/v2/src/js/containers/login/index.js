import { connect } from 'react-redux';
import LoginPage from 'components/login';
import { GET_VERSION } from 'actions/version';

export function mapStateToProps({ auth, status }) {
  return {
    redirectToReferrer: !!auth.loggedIn,
    loading: !!status.loading[GET_VERSION],
  };
}

export default connect(mapStateToProps)(LoginPage);
