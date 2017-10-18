import React from 'react';
import PropTypes from 'prop-types';
import { Redirect } from 'react-router-dom';
import LoginCard from './LoginCard';
import SplashScreen from './Splash';
import { Logo } from './styles';

const LoginPage = ({ redirectToReferrer, location, loading }) => {
  const { from } = location.state || { from: { pathname: '/' } };

  if (redirectToReferrer) {
    return (
      <Redirect to={from} />
    );
  }

  if (loading) {
    return <SplashScreen />;
  }

  return (
    <div>
      <Logo />
      <LoginCard />
    </div>
  );
};

LoginPage.propTypes = {
  location: PropTypes.object.isRequired,
  redirectToReferrer: PropTypes.bool.isRequired,
  loading: PropTypes.bool.isRequired,
};

export default LoginPage;
