import { connect } from 'react-redux';
import Splash from 'components/splash';
import { LOGIN, checkLogin } from 'actions/auth';

export function mapStateToProps({ status }) {
  return {
    checking: !!status.loading[LOGIN],
  };
}

export function mapDispatchToProps(dispatch) {
  return {
    checkLogin: () => dispatch(checkLogin()),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(Splash);
