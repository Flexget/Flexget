import PropTypes from 'prop-types';

export const HistoryShape = PropTypes.shape({
  task: PropTypes.string,
  title: PropTypes.string,
  url: PropTypes.string,
  filename: PropTypes.string,
  details: PropTypes.string,
  time: PropTypes.strings,
  id: PropTypes.number,
});
