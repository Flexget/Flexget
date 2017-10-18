import React from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { NavLogo } from './styles';

const Logo = ({ sideBarOpen }) => (
  <Link to="/">
    <NavLogo open={sideBarOpen} />
  </Link>
);

Logo.propTypes = {
  sideBarOpen: PropTypes.bool.isRequired,
};

export default Logo;
