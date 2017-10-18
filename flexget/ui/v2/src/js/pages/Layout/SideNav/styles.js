import styled, { css } from 'react-emotion';
import theme from 'theme';
import List from 'material-ui/List';
import SideNavEntry from 'pages/Layout/SideNavEntry';
import Version from 'pages/Layout/Version';

export const NestedSideNavEntry = styled(SideNavEntry)`
  padding-left: ${theme.spacing.unit * 0.4}rem;
`;

export const drawerPaper = open => css`
  position: relative;
  background-color: ${theme.palette.secondary[900]};
  height: calc(100vh - 10rem);
  width: ${open ? '100vw' : 0};
  transition: ${theme.transitions.create('width')};
  border-right: none !important;

  ${theme.breakpoints.up('sm')} {
    height: calc(100vh - 5rem);
    width: ${open ? '19rem' : '6rem'}
  }
`;

export const DrawerInner = styled.div`
  width: inherit;
  height: inherit;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
`;

export const NavVersion = styled(Version)`
  display: ${({ hide }) => (hide ? 'none' : 'block')};
`;

export const NavList = styled(List)`
  width: inherit;
`;
