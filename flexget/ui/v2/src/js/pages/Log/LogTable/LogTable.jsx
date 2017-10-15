import React from 'react';
import PropTypes from 'prop-types';
import { AutoSizer, Column } from 'react-virtualized';
import { LogShape } from 'store/log/shapes';
import 'react-virtualized/styles.css';
import { Table, rowClasses } from './styles';

const LogTable = ({ messages }) => (
  <AutoSizer>
    {({ height, width }) => (
      <Table
        rowCount={messages.length}
        rowHeight={20}
        headerHeight={50}
        width={width}
        height={height}
        rowGetter={({ index }) => messages[index]}
        rowClassName={({ index }) => messages[index] && rowClasses[messages[index]
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
  messages: PropTypes.arrayOf(LogShape).isRequired,
};

export default LogTable;
