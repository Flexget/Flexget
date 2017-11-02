import React from 'react';
import PropTypes from 'prop-types';
import { Spinner, Wrapper } from './styles';

const LoadingBar = ({ loading }) => {
  if (loading) {
    return (
      <Wrapper>
        <Spinner />
      </Wrapper>
    );
  }
  return null;
};

LoadingBar.propTypes = {
  loading: PropTypes.bool,
};

LoadingBar.defaultProps = {
  loading: false,
};

export default LoadingBar;
