import { connect } from 'react-redux';
import { LOGOUT } from 'actions/auth';
import { SERVER_RELOAD, SERVER_SHUTDOWN } from 'actions/server';
import { request } from 'utils/actions';
import Navbar from 'components/layout/Navbar';

function mapDispatchToProps(dispatch) {
  return {
    logout: () => dispatch(request(LOGOUT)),
    reloadServer: () => dispatch(request(SERVER_RELOAD)),
    shutdownServer: () => dispatch(request(SERVER_SHUTDOWN)),
  };
}

export default connect(null, mapDispatchToProps)(Navbar);

