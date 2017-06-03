import { connect } from 'react-redux';
import { logout } from 'actions/auth';
import Navbar from 'components/layout/Navbar';

function mapDispatchToProps(dispatch) {
  return {
    logout: () => dispatch(logout()),
  };
}

export default connect(null, mapDispatchToProps)(Navbar);

