import React from 'react';
import PropTypes from 'prop-types';
import {
  SecondaryAppBar,
  SecondaryToolbar,
} from './styles';

const SecondaryNav = ({ children }) => (
  <SecondaryAppBar>
    <SecondaryToolbar>
      {children}
    </SecondaryToolbar>
  </SecondaryAppBar>
);

SecondaryNav.propTypes = {
  children: PropTypes.node.isRequired,
};

export default SecondaryNav;
