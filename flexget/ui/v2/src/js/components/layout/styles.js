import styled from 'styled-components';
import theme from 'theme';

const HEADER_HEIGHT = 5;
const MOBILE_HEADER_HEIGHT = (HEADER_HEIGHT * 2) - 0.2;
const PADDING = 1;

export const Wrapper = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 100vh;
`;

export const Main = styled.main`
  display: flex;
  flex-direction: row;
  margin-top: ${MOBILE_HEADER_HEIGHT}rem;
  flex: 1;
  ${theme.breakpoints.up('sm')} {
    margin-top: ${HEADER_HEIGHT}rem;
  }
`;

export const Header = styled.header`
  display: flex;
  min-height: ${HEADER_HEIGHT}rem;
  flex-direction: column;
  z-index: 2;
  position: fixed;
  width: 100%;
  ${theme.breakpoints.up('sm')} {
    flex-direction: row;
  }
`;

export const LogoWrapper = styled.div`
  height: ${HEADER_HEIGHT}rem;
`;

export const Nav = styled.nav`
  height: ${HEADER_HEIGHT}rem;
  flex: 1;
`;

export const SideBar = styled.aside`
  overflow-y: auto;
`;

export const Content = styled.section`
  flex: 1;
  padding: ${PADDING}rem;
  overflow-y: auto;
  opacity: 1;
  transition: ${theme.transitions.create(['opacity', 'margin-left'])};
  margin-left: ${({ open }) => (open ? '19rem' : '5rem')};

  ${theme.breakpoints.down('sm')} {
    margin-left: 0;
    padding: ${({ open }) => (open ? 0 : `${PADDING}rem`)};
    opacity: ${({ open }) => (open ? 0 : 1)};
    display: ${({ open }) => (open ? 'none' : 'block')};
  }
`;
