import { connect } from 'react-redux';
import LogTable from 'components/log/LogTable';

export function mapStateToProps({ log }) {
  return {
    messages: log.messages,
  };
}

export default connect(mapStateToProps)(LogTable);
