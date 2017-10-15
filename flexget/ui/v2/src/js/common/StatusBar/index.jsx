import React from 'react';
import PropTypes from 'prop-types';
import SnackBar from 'material-ui/Snackbar';

const StatusBar = ({ open, message, clearStatus }) => (
  <SnackBar
    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
    open={open}
    autoHideDuration={6000}
    onRequestClose={clearStatus}
    SnackbarContentProps={{
      'aria-describedby': 'message-id',
    }}
    message={<span id="message-id">{message}</span>}
  />
);

StatusBar.propTypes = {
  open: PropTypes.bool.isRequired,
  message: PropTypes.string,
  clearStatus: PropTypes.func.isRequired,
};

StatusBar.defaultProps = {
  message: '',
};

export default StatusBar;
