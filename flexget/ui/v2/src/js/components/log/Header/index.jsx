import React, { Component } from 'react';
import PropTypes from 'prop-types';
import classNames from 'classnames';
import { withStyles, createStyleSheet } from 'material-ui/styles';
import Icon from 'material-ui/Icon';
import Menu, { MenuItem } from 'material-ui/Menu';
import TextField from 'material-ui/TextField';
import Typography from 'material-ui/Typography';

const styleSheet = createStyleSheet('LogHeader', theme => ({
  root: {
    display: 'block',
    [theme.breakpoints.up('sm')]: {
      display: 'flex',
      alignItems: 'baseline',
    },
  },
  grey: {
    color: theme.palette.grey[600],
  },
  spacer: {
    flex: {
      grow: 1,
    },
  },
  textFieldWrapper: {
    display: 'flex',
    alignItems: 'baseline',
  },
  input: {
    marginLeft: 10,
    marginRight: 10,
  },
  menuIcon: {
    paddingRight: 30,
  },
  pointer: {
    cursor: 'pointer',
  },
}));

const ENTER_KEY = 13;

class Header extends Component {
  static propTypes = {
    start: PropTypes.func.isRequired,
    connected: PropTypes.bool.isRequired,
    classes: PropTypes.object.isRequired,
    setQuery: PropTypes.func.isRequired,
    query: PropTypes.string.isRequired,
    clearLogs: PropTypes.func.isRequired,
    lines: PropTypes.string.isRequired,
    setLines: PropTypes.func.isRequired,
  };

  state = {
    open: false,
  };


  componentDidMount() {
    this.start();
  }

  componentWillUnmount() {
    this.stop();
  }

  start = () => { this.stream = this.props.start(); }
  stop = () => this.stream && this.stream.abort()
  reload = () => {
    this.stop();
    this.start();
  }
  clearLogs = () => this.props.clearLogs()
  handleLines = event => this.props.setLines(event.target.value)
  handleQuery = event => this.props.setQuery(event.target.value)
  handleKeyPress = event => event.which === ENTER_KEY && this.reload()
  handleRequestClose = () => this.setState({
    open: false,
    anchorEl: undefined,
  })

  handleMenuClick = event => this.setState({
    open: true,
    anchorEl: event.currentTarget,
  })

  render() {
    const { connected, classes, query, lines } = this.props;
    const { anchorEl, open } = this.state;
    const helperText = 'Supports operators and, or, (), and "str"';

    return (
      <div className={classes.root}>
        <div>
          <Typography type="title">
            Server Log
          </Typography>
          <Typography className={classes.grey} type="subheading">
            { connected ? 'Streaming' : 'Disconnected' }
          </Typography>
        </div>
        <div className={classes.spacer} />
        <div className={classes.textFieldWrapper}>
          <Icon className={`fa fa-filter ${classes.grey}`} />
          <TextField
            id="filter"
            label="Filter"
            className={classes.input}
            value={query}
            onChange={this.handleQuery}
            inputProps={{
              onKeyPress: this.handleKeyPress,
            }}
            helperText={helperText}
          />
          <Icon onClick={this.handleMenuClick} className={`fa fa-ellipsis-v ${classes.grey} ${classes.pointer}`} />
        </div>
        <Menu
          id="log-menu"
          anchorEl={anchorEl}
          open={open}
          onRequestClose={this.handleRequestClose}
        >
          <MenuItem>
            <TextField
              id="lines"
              label="Max Lines"
              value={lines}
              onChange={this.handleLines}
              type="number"
              inputProps={{
                onKeyPress: this.handleKeyPress,
              }}
            />
          </MenuItem>
          <MenuItem onClick={this.clearLogs}>
            <Icon className={`${classes.menuIcon} fa fa-eraser`} />
            Clear
          </MenuItem>
          <MenuItem onClick={connected ? this.stop : this.start}>
            <Icon className={
              classNames(classes.menuIcon, 'fa', {
                'fa-play': !connected,
                'fa-stop': connected,
              })}
            />
            {connected ? 'Stop' : 'Start'}
          </MenuItem>
        </Menu>
      </div>
    );
  }
}

export default withStyles(styleSheet)(Header);

