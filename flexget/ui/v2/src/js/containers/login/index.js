import { connect } from 'react-redux';
import LoginPage from 'components/login';

export function mapStateToProps({ auth }) {
  return {
    redirectToReferrer: !!auth.loggedIn,
  };
}

export default connect(mapStateToProps)(LoginPage);
