import styled from 'react-emotion';
import theme from 'theme';
import Paper from 'material-ui/Paper';

export const PaperWrapper = styled(Paper)`
  padding: 2.4rem;
  display: flex;
  flex: 1;
  height: 100%;
  box-sizing: border-box;
  flex-direction: column;
  ${theme.breakpoints.up('sm')} {
    padding-top: 0;
  }
`;

export const Spacer = styled.div`
  flex: 1;
`;

export const NoPaddingWrapper = styled.div`
  height: calc(100% + 2rem);
  margin: -1rem;
  display: flex;
  flex-direction: column;
`;
