import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import Icon from 'material-ui/Icon';
import Menu, { MenuItem } from 'material-ui/Menu';
import Dialog, {
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from 'material-ui/Dialog';
import Button from 'material-ui/Button';
import 'font-awesome/css/font-awesome.css';
import {
  MenuIcon,
  NavAppBar,
  Spacer,
  NavToolbar,
  NavIcon,
} from './styles';

export class Navbar extends Component {
  static propTypes = {
    toggle: PropTypes.func.isRequired,
    logout: PropTypes.func.isRequired,
    reloadServer: PropTypes.func.isRequired,
    shutdownServer: PropTypes.func.isRequired,
  };

  state = {
    menuOpen: false,
    shutdownPrompt: false,
  };

  handleMenuRequestClose = () => this.setState({
    menuOpen: false,
    anchorEl: undefined,
  })

  handleMenuClick = event => this.setState({
    menuOpen: true,
    anchorEl: event.currentTarget,
  })

  handleReloadClick = () => {
    this.props.reloadServer();
    this.handleMenuRequestClose();
  }

  handleShutdownPromptClick = () => {
    this.setState({ shutdownPrompt: true });
    this.handleMenuRequestClose();
  }

  handleShutdownClick = () => {
    this.props.shutdownServer();
    this.handleShutdownRequestClose();
  }

  handleShutdownRequestClose = () => this.setState({
    shutdownPrompt: false,
  });

  render() {
    const { toggle, logout } = this.props;
    const { anchorEl, menuOpen, shutdownPrompt } = this.state;

    return (
      <NavAppBar>
        <NavToolbar>
          <NavIcon onClick={toggle}>
            <Icon className="fa fa-bars" />
          </NavIcon>
          <Spacer />
          <Link to="/config">
            <NavIcon aria-label="Config">
              <Icon className="fa fa-pencil" />
            </NavIcon>
          </Link>
          <Link to="/log">
            <NavIcon aria-label="Log">
              <Icon className="fa fa-file-text-o" />
            </NavIcon>
          </Link>
          <NavIcon
            aria-label="Manage"
            onClick={this.handleMenuClick}
          >
            <Icon className="fa fa-cog" />
          </NavIcon>
          <Menu
            id="nav-menu"
            anchorEl={anchorEl}
            open={menuOpen}
            onRequestClose={this.handleMenuRequestClose}
          >
            <MenuItem onClick={this.handleReloadClick}>
              <MenuIcon className="fa fa-refresh" />
              Reload
            </MenuItem>
            <MenuItem onClick={this.handleShutdownPromptClick}>
              <MenuIcon className="fa fa-power-off" />
              Shutdown
            </MenuItem>
            <MenuItem>
              <MenuIcon className="fa fa-database" />
              Database
            </MenuItem>
            <MenuItem onClick={logout}>
              <MenuIcon className="fa fa-sign-out" />
              Logout
            </MenuItem>
          </Menu>
          <Dialog open={shutdownPrompt} onRequestClose={this.handleShutdownRequestClose}>
            <DialogTitle>Shutdown</DialogTitle>
            <DialogContent>
              <DialogContentText>
                Are you sure you want to shutdown FlexGet?
              </DialogContentText>
            </DialogContent>
            <DialogActions>
              <Button onClick={this.handleShutdownRequestClose} color="primary">
                Cancel
              </Button>
              <Button onClick={this.handleShutdownClick} color="primary">
                Shutdown
              </Button>
            </DialogActions>
          </Dialog>
        </NavToolbar>
      </NavAppBar>
    );
  }
}

export default Navbar;
