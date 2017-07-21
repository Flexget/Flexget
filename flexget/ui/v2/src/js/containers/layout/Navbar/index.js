import { connect } from 'react-redux';
import { logout } from 'actions/auth';
import { reloadServer, shutdownServer } from 'actions/server';
import Navbar from 'components/layout/Navbar';

function mapDispatchToProps(dispatch) {
  return {
    logout: () => dispatch(logout()),
    reloadServer: () => dispatch(reloadServer()),
    shutdownServer: () => dispatch(shutdownServer()),
  };
}

export default connect(null, mapDispatchToProps)(Navbar);

