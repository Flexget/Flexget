import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { withStyles, createStyleSheet } from 'material-ui/styles';
import Logo from 'components/layout/Logo';
import Navbar from 'containers/layout/Navbar';
import SideNav from 'components/layout/Sidenav';

const HEADER_HEIGHT = 50;
const MOBILE_HEADER_HEIGHT = (HEADER_HEIGHT * 2) - 2;
const PADDING = 10;

const scrollMixin = theme => ({
  overflowY: 'auto',
  height: `calc(100vh - ${MOBILE_HEADER_HEIGHT}px)`,
  [theme.breakpoints.up('sm')]: {
    height: `calc(100vh - ${HEADER_HEIGHT}px)`,
  },
});
const styleSheet = createStyleSheet('Layout', theme => ({
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
  layout: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    minHeight: '100vh',
  },
  main: {
    display: 'flex',
    flexDirection: 'row',
    marginTop: MOBILE_HEADER_HEIGHT,
    flex: 1,
    [theme.breakpoints.up('sm')]: {
      marginTop: HEADER_HEIGHT,
    },
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
    height: HEADER_HEIGHT,
  },
  navbar: {
    height: HEADER_HEIGHT,
    flex: 1,
  },
  sidebar: {
    ...scrollMixin(theme),
  },
  content: {
    flex: 1,
    ...scrollMixin(theme),
  },
  pageWrap: {
    padding: PADDING,
  },
}));

class Layout extends Component {
  static propTypes = {
    children: PropTypes.node.isRequired,
    classes: PropTypes.object.isRequired,
    loggedIn: PropTypes.bool.isRequired,
    checkLogin: PropTypes.func.isRequired,
  };

  state = {
    sideBarOpen: false,
  };

  componentDidMount() {
    const { loggedIn, checkLogin } = this.props;
    if (!loggedIn) {
      checkLogin();
    }
  }

  toggleSideBar = () => {
    this.setState({
      sideBarOpen: !this.state.sideBarOpen,
    });
  }

  render() {
    const { children, classes } = this.props;
    const { sideBarOpen } = this.state;

    return (
      <div className={classes.layout}>
        <header className={classes.header}>
          <div className={classes.logo}>
            <Logo sideBarOpen={sideBarOpen} />
          </div>
          <nav className={classes.navbar}>
            <Navbar toggle={this.toggleSideBar} />
          </nav>
        </header>
        <main className={classes.main}>
          <aside className={classes.sideBar}>
            <SideNav sideBarOpen={sideBarOpen} />
          </aside>
          <section className={classes.content}>
            <div className={classes.pageWrap}>
              { children }
            </div>
          </section>
        </main>
      </div>
    );
  }
}

export default withStyles(styleSheet)(Layout);
