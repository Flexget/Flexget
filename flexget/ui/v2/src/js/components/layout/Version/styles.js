import styled, { css } from 'emotion/react';
import theme from 'theme';

export const version = css`color: ${theme.palette.error[500]}`;
export const Wrapper = styled.div`
  composes: ${version};
`;

export const Line = styled.p`
  margin: 0;
`;
