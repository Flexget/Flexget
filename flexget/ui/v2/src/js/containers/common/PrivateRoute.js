import { connect } from 'react-redux';
import PrivateRoute from 'components/common/PrivateRoute';

function mapStateToProps({ auth }) {
  return {
    loggedIn: !!auth.loggedIn,
  };
}

export default connect(mapStateToProps)(PrivateRoute);
