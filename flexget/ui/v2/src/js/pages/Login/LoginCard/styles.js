import styled from 'react-emotion';
import { Field } from 'redux-form';
import MUICard, { CardContent } from 'material-ui/Card';
import Button from 'material-ui/Button';
import theme from 'theme';

export const Card = styled(MUICard)`
  max-width: 40rem;
  margin: 0 1rem;
  ${theme.breakpoints.up('sm')} {
    margin: 0 auto;
  }
`;

export const ErrorMessage = styled.div`
  color: ${theme.palette.error[500]};
  text-align: center;
  padding: 1rem;
`;

export const LoginButton = styled(Button)`
  width: 100%;
`;

export const Content = styled(CardContent)`
  display: flex;
  flex-direction: column;
`;

export const LoginField = styled(Field)`
  padding-bottom: 1rem;
`;
