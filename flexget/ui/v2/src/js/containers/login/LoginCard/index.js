import { connect } from 'react-redux';
import { LOGIN } from 'actions/auth';
import { request } from 'utils/actions';
import LoginCard from 'components/login/LoginCard';

export function mapStateToProps({ status }) {
  return {
    initialValues: {
      username: 'flexget',
    },
    errorStatus: status.error || {},
  };
}

function mapDispatchToProps(dispatch) {
  return {
    onSubmit: credentials => dispatch(request(LOGIN, credentials)),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(LoginCard);
