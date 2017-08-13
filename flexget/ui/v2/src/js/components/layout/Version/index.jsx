import React, { Component } from 'react';
import PropTypes from 'prop-types';
import semver from 'semver-compare';
import IconButton from 'material-ui/IconButton';
import Icon from 'material-ui/Icon';
import { withStyles, createStyleSheet } from 'material-ui/styles';
import 'font-awesome/css/font-awesome.css';

const styleSheet = createStyleSheet('Version', theme => ({
  version: {
    color: theme.palette.error[500],
  },
  par: {
    margin: 0,
  },
}));

class Version extends Component {
  static propTypes = {
    classes: PropTypes.object.isRequired,
    version: PropTypes.shape({
      api: PropTypes.string,
      flexget: PropTypes.string,
      latest: PropTypes.string,
    }).isRequired,
    getVersion: PropTypes.func.isRequired,
  };

  componentDidMount() {
    this.props.getVersion();
  }

  render() {
    const { classes, version: { api, flexget, latest } } = this.props;
    return (
      <div className={classes.version}>
        <p className={classes.par}>Version Info</p>
        <p className={classes.par}>Flexget: { flexget } {
          latest && semver(latest, flexget) === 1 && (
            <IconButton href="https://flexget.com/ChangeLog">
              <Icon className={`fa fa-question-circle-o ${classes.version}`} />
            </IconButton>
          ) } </p>
        <p className={classes.par}>API: { api }</p>
      </div>
    );
  }
}

export default withStyles(styleSheet)(Version);
