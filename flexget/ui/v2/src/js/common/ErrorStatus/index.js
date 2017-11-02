import { connect } from 'react-redux';
import StatusBar from '../StatusBar';
import { clearStatus } from '../../store/status/actions';

export function mapStateToProps({ status }) {
  return {
    open: !!status.error,
    message: status.error && status.error.message,
  };
}

export function mapDispatchToProps(dispatch) {
  return {
    clearStatus: () => dispatch(clearStatus()),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(StatusBar);
