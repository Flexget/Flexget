import { connect } from 'react-redux';
import PrivateRoute from './PrivateRoute';

export function mapStateToProps({ auth }) {
  return {
    loggedIn: !!auth.loggedIn,
  };
}

export default connect(mapStateToProps)(PrivateRoute);
export { PrivateRoute };
