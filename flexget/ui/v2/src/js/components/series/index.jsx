import React from 'react';
import PropTypes from 'prop-types';
import { withStyles, createStyleSheet } from 'material-ui/styles';

const styleSheet = createStyleSheet('Series', theme => ({
}));

const SeriesPage = ({ classes }) => (
  <div>
  </div>
);

SeriesPage.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default withStyles(styleSheet)(SeriesPage);

