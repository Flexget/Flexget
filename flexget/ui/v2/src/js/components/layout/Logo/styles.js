import styled from 'emotion/react';
import theme from 'theme';
import headerImage from 'images/header.png';

export const NavLogo = styled.div`
  background: ${theme.palette.accent[900]} url(${headerImage}) no-repeat center;
  background-size: 17.5rem;
  height: 100%;
  transition: ${theme.transitions.create('width')};
  ${theme.breakpoints.up('sm')} {
    width: ${({ open }) => (open ? '19rem' : '5rem')};
    background-size: ${({ open }) => (open ? '17.5rem' : '24rem')};
  }
`;
