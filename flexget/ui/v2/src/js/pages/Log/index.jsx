import React from 'react';
import { PaperWrapper } from 'common/styles';
import Header from './Header';
import LogTable from './LogTable';
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
