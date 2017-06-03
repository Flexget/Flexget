import React from 'react';
import PropTypes from 'prop-types';
import classNames from 'classnames';
import { Link } from 'react-router-dom';
import headerImage from 'images/header.png';
import { withStyles, createStyleSheet } from 'material-ui/styles';

const styleSheet = createStyleSheet('Logo', theme => ({
  logo: {
    background: `${theme.palette.accent[900]} url(${headerImage}) no-repeat center`,
    backgroundSize: 175,
    height: '100%',
    transition: theme.transitions.create('width'),
    [theme.breakpoints.up('sm')]: {
      width: 190,
    },
  },
  logoMini: {
    [theme.breakpoints.up('sm')]: {
      backgroundSize: 240,
      width: 50,
    },
  },
}));

const Logo = ({ classes, sideBarOpen }) => (
  <Link to="/">
    <div className={
      classNames(
        classes.logo,
        { [classes.logoMini]: !sideBarOpen },
      )}
    />
  </Link>
);


Logo.propTypes = {
  classes: PropTypes.object.isRequired,
  sideBarOpen: PropTypes.bool.isRequired,
};

export default withStyles(styleSheet)(Logo);
