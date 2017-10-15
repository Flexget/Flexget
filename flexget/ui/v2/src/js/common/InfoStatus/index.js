import { connect } from 'react-redux';
import StatusBar from 'common/StatusBar';
import { clearStatus } from 'store/status/actions';

export function mapStateToProps({ status }) {
  return {
    open: !!status.info,
    message: status.info,
  };
}

export function mapDispatchToProps(dispatch) {
  return {
    clearStatus: () => dispatch(clearStatus()),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(StatusBar);
