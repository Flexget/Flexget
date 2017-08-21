import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from 'material-ui/styles';
import { AutoSizer, Table, Column } from 'react-virtualized';
import 'react-virtualized/styles.css';

const styleSheet = () => ({
  table: {
    fontSize: 10,
  },
  error: {
    backgroundColor: '#f2dede',
  },
  critical: {
    backgroundColor: '#f2dede',
  },
  warning: {
    backgroundColor: '#fcf8e3',
  },
});

const LogTable = ({ messages, classes }) => (
  <AutoSizer>
    {({ height, width }) => (
      <Table
        className={classes.table}
        rowCount={messages.length}
        rowHeight={20}
        headerHeight={50}
        width={width}
        height={height}
        rowGetter={({ index }) => messages[index]}
        rowClassName={({ index }) => messages[index] && classes[messages[index]
          .log_level.toLowerCase()]}
      >
        <Column
          label="Time"
          dataKey="timestamp"
          width={100}
        />
        <Column
          label="Level"
          dataKey="log_level"
          width={100}
        />
        <Column
          label="Plugin"
          dataKey="plugin"
          width={100}
        />
        <Column
          label="Task"
          dataKey="task"
          width={100}
        />
        <Column
          label="Message"
          dataKey="message"
          width={100}
          flexGrow={1}
        />
      </Table>
    )}
  </AutoSizer>
);

LogTable.propTypes = {
  messages: PropTypes.arrayOf(PropTypes.shape({
    timestamp: PropTypes.string,
    message: PropTypes.string,
    task: PropTypes.string,
    log_level: PropTypes.string,
    plugin: PropTypes.string,
  })).isRequired,
  classes: PropTypes.object.isRequired,
};

export default withStyles(styleSheet)(LogTable);
