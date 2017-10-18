import { connect } from 'react-redux';
import {
  LOG_CONNECT,
  LOG_DISCONNECT,
  LOG_CLEAR,
} from 'store/log/actions';
import { action, request } from 'utils/actions';
import Header from './Header';

export function mapStateToProps({ log }) {
  return {
    connected: log.connected,
  };
}

function mapDispatchToProps(dispatch) {
  return {
    start: payload => dispatch(request(LOG_CONNECT, payload)),
    stop: () => dispatch(request(LOG_DISCONNECT)),
    clearLogs: () => dispatch(action(LOG_CLEAR)),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(Header);
export { Header };
