import React from 'react';
import Header from 'containers/log/Header';
import LogTable from 'containers/log/LogTable';
import {
  LogWrapper,
  TableWrapper,
} from './styles';

const LogPage = () => (
  <LogWrapper elevation={4}>
    <Header />
    <TableWrapper>
      <LogTable />
    </TableWrapper>
  </LogWrapper>
);

export default LogPage;
