import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from 'material-ui/styles';
import { LinearProgress } from 'material-ui/Progress';

const styleSheet = theme => ({
  root: {
    position: 'relative',
    overflow: 'hidden',
    height: 5,
    backgroundColor: theme.palette.accent[100],
  },
  bar: {
    position: 'absolute',
    left: 0,
    bottom: 0,
    top: 0,
    transition: 'transform 0.2s linear',
    backgroundColor: theme.palette.accent[500],
  },
});


const LoadingBar = ({ loading, classes }) => {
  if (loading) {
    return (
      <LinearProgress
        mode="query"
        classes={{
          root: classes.root,
          bar: classes.bar,
        }}
      />
    );
  }
  return null;
};

LoadingBar.propTypes = {
  loading: PropTypes.bool,
  classes: PropTypes.object.isRequired,
};

LoadingBar.defaultProps = {
  loading: false,
};

export default withStyles(styleSheet)(LoadingBar);
