import React from 'react';
import Header from 'containers/log/Header';
import LogTable from 'containers/log/LogTable';
import { PaperWrapper } from 'components/common/styles';
import { TableWrapper } from './styles';

const LogPage = () => (
  <PaperWrapper elevation={4}>
    <Header />
    <TableWrapper>
      <LogTable />
    </TableWrapper>
  </PaperWrapper>
);

export default LogPage;
