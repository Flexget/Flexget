import styled, { css } from 'react-emotion';
import { Table as RVTable } from 'react-virtualized';

export const Table = styled(RVTable)`
  font-size: 1rem;
`;

export const rowClasses = {
  error: css`background-color: #f2dede`,
  critical: css`background-color: #f2dede`,
  warning: css`background-color: #fcf8e3`,
};
