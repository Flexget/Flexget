import styled from 'react-emotion';
import theme from 'theme';

const HEADER_HEIGHT = 5;
const MOBILE_HEADER_HEIGHT = (HEADER_HEIGHT * 2);

export const Wrapper = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 100vh;
`;

export const Main = styled.main`
  display: flex;
  flex-direction: row;
  padding-top: ${MOBILE_HEADER_HEIGHT}rem;
  flex: 1;
  height: 100vh;
  ${theme.breakpoints.up('sm')} {
    padding-top: ${HEADER_HEIGHT}rem;
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
  overflow-y: auto;
  padding: 1rem;
  opacity: 1;
  transition: ${theme.transitions.create(['opacity', 'margin-left'])};

  ${theme.breakpoints.down('sm')} {
    margin-left: 0;
    opacity: ${({ open }) => (open ? 0 : 1)};
    display: ${({ open }) => (open ? 'none' : 'block')};
  }
`;
