import React from 'react';
import PropTypes from 'prop-types';
import headerImage from 'images/header.png';
import { withStyles, createStyleSheet } from 'material-ui/styles';

const styleSheet = createStyleSheet('Logo', theme => ({
  logo: {
    background: `${theme.palette.accent[900]} url(${headerImage}) no-repeat center`,
    backgroundSize: '175px',
    transition: 'width 0.5s ease',
    height: '100%',
    width: '100%',
  },
}));

const Logo = ({ classes }) => <div className={classes.logo} />;

Logo.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default withStyles(styleSheet)(Logo);
