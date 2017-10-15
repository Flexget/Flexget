import styled, { keyframes } from 'react-emotion';
import theme from 'theme';

const stretchDelay = keyframes`
  0%, 40%, 100% {
    transform: scaleY(0.4);
  }

  20% {
    transform: scaleY(1.0);
  }
`;

export const Spinner = styled.div`
  margin: 10rem auto;
  width: 5rem;
  height: 4rem;
  text-align: center;
  font-size: 1rem;
`;

export const Rect1 = styled.div`
  background-color: ${theme.palette.primary[500]};
  height: 100%;
  width: 0.6rem;
  display: inline-block;
  margin: 0.1rem;
  animation: ${stretchDelay} 1.2s infinite ease-in-out;
`;

export const Rect2 = styled(Rect1)`
  animation-delay: -1.1s;
`;

export const Rect3 = styled(Rect1)`
  animation-delay: -1.0s;
`;

export const Rect4 = styled(Rect1)`
  animation-delay: -0.9s;
`;

export const Rect5 = styled(Rect1)`
  animation-delay: -0.8s;
`;
