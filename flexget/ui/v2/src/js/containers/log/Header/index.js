import { connect } from 'react-redux';
import {
  startLogStream,
  setLines,
  setQuery,
  clearLogs,
} from 'actions/log';
import Header from 'components/log/Header';

function mapStateToProps({ log }) {
  return {
    connected: log.connected,
    lines: log.lines,
    query: log.query,
  };
}

function mapDispatchToProps(dispatch) {
  return {
    start: () => dispatch(startLogStream()),
    setLines: lines => dispatch(setLines(lines)),
    setQuery: query => dispatch(setQuery(query)),
    clearLogs: () => dispatch(clearLogs()),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(Header);
