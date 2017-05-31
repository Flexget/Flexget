import React from 'react';
import PropTypes from 'prop-types';
import { withStyles, createStyleSheet } from 'material-ui/styles';

const SIDEBAR_WIDTH = '190px';
const HEADER_HEIGHT = '50px';

const styleSheet = createStyleSheet('Layout', theme => ({
  layout: {
    backgroundColor: theme.palette.background.default,
    fontFamily: 'Roboto',
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
  },
  main: {
    display: 'flex',
    flexDirection: 'row',
    height: '100%',
  },
  header: {
    display: 'flex',
    flexDirection: 'row',
    height: HEADER_HEIGHT,
  },
  logo: {
    width: SIDEBAR_WIDTH,
  },
  navbar: {
    flex: 1,
  },
  sidebar: {
    width: SIDEBAR_WIDTH,
  },
  content: {
    flex: 1,
  },
}));

const Layout = ({ children, classes }) => (
  <div className={classes.layout}>
    <div className={classes.header}>
      <div className={classes.logo}>
        LOGO
      </div>
      <div className={classes.navbar}>
        navbar
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
