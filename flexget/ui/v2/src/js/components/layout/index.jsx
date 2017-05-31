import React from 'react';
import PropTypes from 'prop-types';
import { withStyles, createStyleSheet } from 'material-ui/styles';
import Logo from 'components/layout/logo';

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
    minHeight: HEADER_HEIGHT,
    flexDirection: 'column',
    [theme.media[1024]]: {
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
  },
  content: {
    flex: 1,
  },
}));

const Layout = ({ children, classes }) => (
  <div className={classes.layout}>
    <div className={classes.header}>
      <div className={classes.logo}>
        <Logo />
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
