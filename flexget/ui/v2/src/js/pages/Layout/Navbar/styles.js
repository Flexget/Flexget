import styled, { css } from 'react-emotion';
import AppBar from 'material-ui/AppBar';
import Toolbar from 'material-ui/Toolbar';
import IconButton from 'material-ui/IconButton';
import Icon from 'material-ui/Icon';
import theme from 'theme';

export const menuIcon = css`padding-right: 3rem`;

export const NavAppBar = styled(AppBar)`
  position: static;
`;

export const NavToolbar = styled(Toolbar)`
  background-color: ${theme.palette.primary[800]};
  color: ${theme.palette.getContrastText(theme.palette.primary[800])};
  min-height: 5rem;
`;

export const NavIcon = styled(IconButton)`
  color: ${theme.palette.getContrastText(theme.palette.primary[800])};
`;

export const MenuIcon = styled(Icon)`
  padding-right: 3rem;
`;
