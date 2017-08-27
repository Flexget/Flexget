import React, { Component } from 'react';
import PropTypes from 'prop-types';
import Logo from 'components/layout/Logo';
import Navbar from 'containers/layout/Navbar';
import SideNav from 'components/layout/Sidenav';
import LoadingBar from 'containers/common/LoadingBar';
import ErrorStatus from 'containers/common/ErrorStatus';
import InfoStatus from 'containers/common/InfoStatus';
import {
  Wrapper,
  Main,
  Header,
  LogoWrapper,
  Nav,
  SideBar,
  Content,
} from 'components/layout/styles';

class Layout extends Component {
  static propTypes = {
    children: PropTypes.node.isRequired,
  };

  static defaultProps = {
    loggedIn: false,
  };

  state = {
    sideBarOpen: (window.matchMedia && !!window.matchMedia('(min-width: 600px)').matches) || false,
  };

  toggleSideBar = () => {
    this.setState({
      sideBarOpen: !this.state.sideBarOpen,
    });
  }

  render() {
    const { children } = this.props;
    const { sideBarOpen } = this.state;

    return (
      <Wrapper>
        <Header>
          <LogoWrapper>
            <Logo sideBarOpen={sideBarOpen} />
          </LogoWrapper>
          <Nav>
            <Navbar toggle={this.toggleSideBar} />
            <LoadingBar />
          </Nav>
        </Header>
        <Main>
          <SideBar>
            <SideNav
              sideBarOpen={sideBarOpen}
              toggle={this.toggleSideBar}
            />
          </SideBar>
          <Content open={sideBarOpen}>
            { children }
          </Content>
          <ErrorStatus />
          <InfoStatus />
        </Main>
      </Wrapper>
    );
  }
}

export default Layout;
