import React from 'react';
import PropTypes from 'prop-types';
import { Field, reduxForm } from 'redux-form';
import Button from 'material-ui/Button';
import Card, { CardActions, CardContent } from 'material-ui/Card';
import { withStyles } from 'material-ui/styles';
import TextField from 'components/common/TextField';

const styleSheet = theme => ({
  card: {
    maxWidth: 400,
    margin: '0 10px',
    [theme.breakpoints.up('sm')]: {
      margin: '0 auto',
    },
  },
  error: {
    color: theme.palette.error[500],
    textAlign: 'center',
    padding: 10,
  },
  button: {
    width: '100%',
  },
  cardContent: {
    display: 'flex',
    flex: {
      direction: 'column',
    },
  },
  field: {
    paddingBottom: 10,
  },
});

export const LoginCard = ({ classes, handleSubmit, errorStatus }) => (
  <Card className={classes.card}>
    <form onSubmit={handleSubmit}>
      <CardContent className={classes.cardContent}>
        <div className={classes.error}>
          {errorStatus.message}
        </div>
        <Field
          name="username"
          component={TextField}
          id="username"
          label="Username"
          className={classes.field}
        />
        <Field
          name="password"
          component={TextField}
          id="password"
          label="Password"
          type="Password"
          className={classes.field}
        />
      </CardContent>
      <CardActions>
        <Button type="submit" className={classes.button}>
          Login
        </Button>
      </CardActions>
    </form>
  </Card>
);

LoginCard.propTypes = {
  classes: PropTypes.object.isRequired,
  handleSubmit: PropTypes.func.isRequired,
  errorStatus: PropTypes.object,
};

LoginCard.defaultProps = {
  errorStatus: {},
};

export default reduxForm({
  form: 'login',
})(withStyles(styleSheet)(LoginCard));
