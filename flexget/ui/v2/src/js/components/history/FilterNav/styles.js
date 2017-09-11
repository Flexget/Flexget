import styled from 'emotion/react';
import Icon from 'material-ui/Icon';
import { FormControl } from 'material-ui/Form';
import theme from 'theme';

export const RotatingIcon = styled(Icon)`
  composes: ${'fa fa-chevron-up'};
  transition: ${theme.transitions.create()};
  transform: ${({ rotate }) => rotate && 'rotate(180deg)'};
`;

export const PaddedFormControl = styled(FormControl)`
  margin: 0.5rem 2rem 0.5rem;
`;
