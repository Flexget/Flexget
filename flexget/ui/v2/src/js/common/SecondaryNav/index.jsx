import React from 'react';
import PropTypes from 'prop-types';
import { MuiThemeProvider } from 'material-ui/styles';
import { darkTheme } from 'theme';
import {
  SecondaryAppBar,
  SecondaryToolbar,
} from './styles';

const SecondaryNav = ({ children }) => (
  <MuiThemeProvider theme={darkTheme}>
    <SecondaryAppBar>
      <SecondaryToolbar>
        {children}
      </SecondaryToolbar>
    </SecondaryAppBar>
  </MuiThemeProvider>
);

SecondaryNav.propTypes = {
  children: PropTypes.node.isRequired,
};

export default SecondaryNav;
