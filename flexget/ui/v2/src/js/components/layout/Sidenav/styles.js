import styled, { css } from 'styled-components';
import theme from 'theme';
import Paper from 'material-ui/Paper';
import List, { ListItem } from 'material-ui/List';
import Button from 'material-ui/Button';

export const colorClass = css`color: ${theme.palette.accent[200]};`;

export const ListWrapper = styled(Paper)`
  background-color: ${theme.palette.accent[900]};
  transition: ${theme.transitions.create(['width', 'visibility'])};
  height: auto;
  width: ${({ open }) => (open ? '100vw' : 0)};
  border-radius: 0;
  display: flex;
  flex-direction: column;
  visibility: ${({ open }) => (open ? 'visible' : 'hidden')};

  ${theme.breakpoints.up('sm')} {
    height: calc(100% - 5rem);
    width: ${({ open }) => (open ? '19rem' : '5rem')};
    position: fixed;
    visibility: visible;
  }
`;

export const Label = styled.p`
  composes: ${colorClass};
  flex: 1;
  text-transform: none;
  visibility: ${({ open }) => (open ? 'visible' : 'hidden')};
  opacity: ${({ open }) => (open ? 1 : 0)};
  transition: ${theme.transitions.create(['visibility', 'opacity'])};
  width: ${({ open }) => (open ? 'auto' : 0)};
`;

export const NavList = styled(List)`
  flex: 1;
`;

export const NavItem = styled(ListItem)`
  padding: 0;
  height: 4.8rem;
  border-left: 3px solid transparent;

  &:hover {
    border-left: 3px solid ${theme.palette.primary[500]};
  }
`;

export const NavButton = styled(Button)`
  display: flex;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-width: 5rem;
  padding-top: 0;
  padding-bottom: 0;
`;

export const NavVersion = styled.div`
  display: ${({ hide }) => (hide ? 'none' : 'block')};
`;
