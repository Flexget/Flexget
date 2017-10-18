import React from 'react';
import PropTypes from 'prop-types';
import { reduxForm } from 'redux-form';
import { CardActions } from 'material-ui/Card';
import TextField from 'common/TextField';
import {
  Card,
  ErrorMessage,
  LoginButton,
  Content,
  LoginField,
} from './styles';

export const LoginCard = ({ handleSubmit, errorStatus }) => (
  <Card>
    <form onSubmit={handleSubmit}>
      <Content>
        <ErrorMessage>
          {errorStatus.message}
        </ErrorMessage>
        <LoginField
          name="username"
          component={TextField}
          id="username"
          label="Username"
        />
        <LoginField
          name="password"
          component={TextField}
          id="password"
          label="Password"
          type="Password"
        />
      </Content>
      <CardActions>
        <LoginButton type="submit">
          Login
        </LoginButton>
      </CardActions>
    </form>
  </Card>
);

LoginCard.propTypes = {
  handleSubmit: PropTypes.func.isRequired,
  errorStatus: PropTypes.object,
};

LoginCard.defaultProps = {
  errorStatus: {},
};

export default reduxForm({
  form: 'login',
})(LoginCard);
