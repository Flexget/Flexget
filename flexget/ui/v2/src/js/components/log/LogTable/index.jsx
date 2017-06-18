import React from 'react';
import PropTypes from 'prop-types';
import { withStyles, createStyleSheet } from 'material-ui/styles';
import { AutoSizer, Table, Column } from 'react-virtualized';
import 'react-virtualized/styles.css';

const styleSheet = createStyleSheet('LogTable', () => ({
  table: {
    overflowY: 'scroll',
  },
}));

const LogTable = ({ messages }) => (
  <AutoSizer>
    {({ height, width }) => (
      <Table
        rowCount={messages.length}
        rowHeight={50}
        headerHeight={50}
        width={width}
        height={height}
        rowGetter={({ index }) => messages[index]}
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
};

export default withStyles(styleSheet)(LogTable);
