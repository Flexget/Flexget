import styled from 'styled-components';
import Paper from 'material-ui/Paper';
import theme from 'theme';

export const LogWrapper = styled(Paper)`
  padding: 2.4rem;
  display: flex;
  height: 100%;
  box-sizing: border-box;
  flex-direction: column;
  ${theme.breakpoints.up('sm')} {
    padding-top: 0;
  }
`;

export const TableWrapper = styled.div`
  width: initial;
  flex: 1;
`;
