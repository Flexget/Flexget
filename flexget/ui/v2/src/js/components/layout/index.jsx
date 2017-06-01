import React from 'react';
import PropTypes from 'prop-types';
import { withStyles, createStyleSheet } from 'material-ui/styles';
import Logo from 'components/layout/logo';
import Navbar from 'components/layout/navbar';

const SIDEBAR_WIDTH = 190;
const HEADER_HEIGHT = 50;
const PADDING = 10;

const styleSheet = createStyleSheet('Layout', theme => ({
  layout: {
    backgroundColor: theme.palette.background.default,
    fontFamily: 'Roboto',
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    minHeight: '100vh',
  },
  main: {
    display: 'flex',
    flexDirection: 'row',
    marginTop: HEADER_HEIGHT,
    height: '100%',
  },
  header: {
    display: 'flex',
    minHeight: HEADER_HEIGHT,
    flexDirection: 'column',
    zIndex: 2,
    position: 'fixed',
    width: '100%',
    [theme.breakpoints.up('sm')]: {
      flexDirection: 'row',
    },
  },
  logo: {
    minWidth: SIDEBAR_WIDTH,
    height: HEADER_HEIGHT,
  },
  navbar: {
    height: HEADER_HEIGHT,
    flex: 1,
  },
  sidebar: {
    width: SIDEBAR_WIDTH,
    padding: PADDING,
  },
  content: {
    flex: 1,
    position: 'relative',
    overflowY: 'auto',
    padding: PADDING,
  },
}));

const Layout = ({ children, classes }) => (
  <div className={classes.layout}>
    <div className={classes.header}>
      <div className={classes.logo}>
        <Logo />
      </div>
      <div className={classes.navbar}>
        <Navbar />
      </div>
    </div>
    <div className={classes.main}>
      <div className={classes.sidebar}>
        SIDEBAR
      </div>
      <div className={classes.content}>
        { children }
      </div>
    </div>
  </div>
);

Layout.propTypes = {
  children: PropTypes.node.isRequired,
  classes: PropTypes.object.isRequired,
};

export default withStyles(styleSheet)(Layout);
