import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from 'material-ui/styles';
import Paper from 'material-ui/Paper';
import Header from 'containers/log/Header';
import LogTable from 'containers/log/LogTable';

const styleSheet = theme => ({
  root: {
    padding: 24,
    display: 'flex',
    height: '100%',
    boxSizing: 'border-box',
    flexDirection: 'column',
    [theme.breakpoints.up('sm')]: {
      paddingTop: 0,
    },
  },
  logTable: {
    width: 'initial',
    flex: {
      grow: 1,
    },
  },
});

const LogPage = ({ classes }) => (
  <Paper className={classes.root} elevation={4}>
    <Header />
    <div className={classes.logTable}>
      <LogTable />
    </div>
  </Paper>
);

LogPage.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default withStyles(styleSheet)(LogPage);
