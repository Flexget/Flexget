import styled, { css } from 'react-emotion';
import theme from 'theme';
import Icon from 'material-ui/Icon';
import { ListItem, ListItemText } from 'material-ui/List';

const colorClass = css`color: ${theme.palette.secondary[200]};`;

export const SideNavIcon = styled(Icon)`
  ${colorClass};
`;

export const SideNavText = styled(ListItemText)`
  ${colorClass};
`;

export const NavItem = styled(ListItem)`
  border-left: 3px solid transparent;
  cursor: pointer;

  &:hover {
    border-left: 3px solid ${theme.palette.primary[500]};
  }
`;
