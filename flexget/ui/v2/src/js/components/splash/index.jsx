import React, { Component } from 'react';
import headerImage from 'images/header.png';
import PropTypes from 'prop-types';
import { withStyles } from 'material-ui/styles';
import 'spinkit/css/spinkit.css';

const styleSheet = theme => ({
  '@global': {
    body: {
      height: '100%',
      width: '100%',
      backgroundColor: theme.palette.background.contentFrame,
      fontFamily: 'Roboto',
    },
    a: {
      textDecoration: 'none',
    },
  },
  logo: {
    background: `transparent url(${headerImage}) no-repeat center`,
    minHeight: 90,
    backgroundSize: '100% auto',
    margin: '0 10px',
    [theme.breakpoints.up('sm')]: {
      backgroundSize: 'auto',
    },
  },
});

class SplashScreen extends Component {
  static propTypes = {
    checkLogin: PropTypes.func.isRequired,
    checking: PropTypes.bool.isRequired,
    children: PropTypes.node.isRequired,
    classes: PropTypes.object.isRequired,
  };

  componentDidMount() {
    this.props.checkLogin();
  }

  render() {
    const { classes, checking, children } = this.props;
    if (checking) {
      return (
        <div>
          <div className={classes.logo} />
          <div className="sk-wave">
            <div className="sk-rect sk-rect1" />
            <div className="sk-rect sk-rect2" />
            <div className="sk-rect sk-rect3" />
            <div className="sk-rect sk-rect4" />
            <div className="sk-rect sk-rect5" />
          </div>
        </div>
      );
    }

    return (<div>{children}</div>);
  }
}

export default withStyles(styleSheet)(SplashScreen);
