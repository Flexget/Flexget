import { connect } from 'react-redux';
import { login } from 'actions/auth';
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
    onSubmit: credentials => dispatch(login(credentials)),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(LoginCard);
