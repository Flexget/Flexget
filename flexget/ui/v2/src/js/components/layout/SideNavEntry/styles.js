import styled, { css } from 'emotion/react';
import theme from 'theme';
import Icon from 'material-ui/Icon';
import { ListItem, ListItemText } from 'material-ui/List';

const colorClass = css`color: ${theme.palette.secondary[200]};`;

export const SideNavIcon = styled(Icon)`
  composes: ${colorClass};
`;

export const SideNavText = styled(ListItemText)`
  composes: ${colorClass};
`;

export const NavItem = styled(ListItem)`
  border-left: 3px solid transparent;
  cursor: pointer;

  &:hover {
    border-left: 3px solid ${theme.palette.primary[500]};
  }
`;
