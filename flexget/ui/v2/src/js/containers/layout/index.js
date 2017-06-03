import { connect } from 'react-redux';
import { checkLogin } from 'actions/auth';
import Layout from 'components/layout';

function mapStateToProps({ auth }) {
  return {
    loggedIn: !!auth.loggedIn,
  };
}

function mapDispatchToProps(dispatch) {
  return {
    checkLogin: () => dispatch(checkLogin()),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(Layout);
