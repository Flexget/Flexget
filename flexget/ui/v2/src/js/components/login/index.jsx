import React from 'react';
import PropTypes from 'prop-types';
import { Redirect } from 'react-router-dom';
import headerImage from 'images/header.png';
import { withStyles, createStyleSheet } from 'material-ui/styles';
import LoginCard from 'containers/login/LoginCard';

const styleSheet = createStyleSheet('LoginPage', theme => ({
  logo: {
    background: `transparent url(${headerImage}) no-repeat center`,
    minHeight: 90,
    backgroundSize: '100% auto',
    margin: '0 10px',
    [theme.breakpoints.up('sm')]: {
      backgroundSize: 'auto',
    },
  },
}));

const LoginPage = ({ classes, redirectToReferrer, location }) => {
  const { from } = location.state || { from: { pathname: '/' } };

  if (redirectToReferrer) {
    return (
      <Redirect to={from} />
    );
  }

  return (
    <div>
      <div className={classes.logo} />
      <LoginCard />
    </div>
  );
};

LoginPage.propTypes = {
  classes: PropTypes.object.isRequired,
  location: PropTypes.object.isRequired,
  redirectToReferrer: PropTypes.bool.isRequired,
};

export default withStyles(styleSheet)(LoginPage);
