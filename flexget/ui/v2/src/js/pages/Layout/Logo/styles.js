import styled from 'react-emotion';
import theme from 'theme';
import headerImage from 'images/header.png';

export const NavLogo = styled.div`
  background: ${theme.palette.secondary[900]} url(${headerImage}) no-repeat center;
  background-size: 17.5rem;
  height: 100%;
  transition: ${theme.transitions.create(['width', 'background-size'])};
  ${theme.breakpoints.up('sm')} {
    width: ${({ open }) => (open ? '19rem' : '6rem')};
    background-size: ${({ open }) => (open ? '17.5rem' : '25rem')};
  }
`;
