import styled from 'react-emotion';
import Card, { CardActions, CardHeader } from 'material-ui/Card';
import theme from 'theme';

export const InfoCardWrapper = styled(Card)`
  margin: 0 auto;
  ${theme.breakpoints.up('sm')} {
    width: 50%;
  }
`;

export const InfoCardHeader = styled(CardHeader)`
  background-color: ${theme.palette.primary[800]};
`;

export const BoldParagraph = styled.p`
  font-weight: bold;
`;

export const InfoCardActions = styled(CardActions)`
  justify-content: center;
`;
