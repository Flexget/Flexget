import styled, { css } from 'react-emotion';
import theme from 'theme';

export const version = css`color: ${theme.palette.error[500]}`;
export const Wrapper = styled.div`
  ${version};
`;

export const Line = styled.p`
  margin: 0;
`;
