import React, { Component } from 'react';
import PropTypes from 'prop-types';
import classNames from 'classnames';
import Menu, { MenuItem } from 'material-ui/Menu';
import TextField from 'material-ui/TextField';
import Typography from 'material-ui/Typography';
import {
  Wrapper,
  GreyIcon,
  GreyClickableIcon,
  GreyType,
  Spacer,
  TextFieldWrapper,
  FilterField,
  MenuIcon,
} from './styles';

const ENTER_KEY = 13;

class Header extends Component {
  static propTypes = {
    start: PropTypes.func.isRequired,
    stop: PropTypes.func.isRequired,
    connected: PropTypes.bool.isRequired,
    clearLogs: PropTypes.func.isRequired,
  };

  state = {
    open: false,
    lines: '200',
    query: '',
  };


  componentDidMount() {
    this.reload();
  }

  componentWillUnmount() {
    this.props.stop();
  }

  reload = () => {
    const { connected, start, stop } = this.props;
    const { lines, query } = this.state;

    if (connected) {
      stop();
    }
    start({ lines, query });
  }
  clearLogs = () => this.props.clearLogs()
  handleLines = event => this.setState({ lines: event.target.value })
  handleQuery = event => this.setState({ query: event.target.value })
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
    const { connected, stop } = this.props;
    const { anchorEl, open, query, lines } = this.state;
    const helperText = 'Supports operators and, or, (), and "str"';

    return (
      <Wrapper>
        <div>
          <Typography type="title">
            Server Log
          </Typography>
          <GreyType type="subheading">
            { connected ? 'Streaming' : 'Disconnected' }
          </GreyType>
        </div>
        <Spacer />
        <TextFieldWrapper>
          <GreyIcon className="fa fa-filter" />
          <FilterField
            id="filter"
            label="Filter"
            value={query}
            onChange={this.handleQuery}
            inputProps={{
              onKeyPress: this.handleKeyPress,
            }}
            helperText={helperText}
          />
          <GreyClickableIcon onClick={this.handleMenuClick} className="fa fa-ellipsis-v" />
        </TextFieldWrapper>
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
            <MenuIcon className="fa fa-eraser" />
            Clear
          </MenuItem>
          <MenuItem onClick={connected ? stop : this.reload}>
            <MenuIcon className={
              classNames('fa', {
                'fa-play': !connected,
                'fa-stop': connected,
              })}
            />
            {connected ? 'Stop' : 'Start'}
          </MenuItem>
        </Menu>
      </Wrapper>
    );
  }
}

export default Header;
