import PropTypes from 'prop-types';

export const LogShape = PropTypes.shape({
  timestamp: PropTypes.string,
  message: PropTypes.string,
  task: PropTypes.string,
  log_level: PropTypes.string,
  plugin: PropTypes.string,
});
