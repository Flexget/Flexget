import { connect } from 'react-redux';
import HistoryPage from 'components/history';
import { request } from 'utils/actions';
import { GET_HISTORY } from 'store/history/actions';

function mapDispatchToProps(dispatch) {
  return {
    getHistory: data => dispatch(request(GET_HISTORY, data)),
  };
}

export default connect(null, mapDispatchToProps)(HistoryPage);
