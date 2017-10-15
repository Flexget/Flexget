import { connect } from 'react-redux';
import { request } from 'utils/actions';
import { GET_HISTORY } from 'store/history/actions';
import History from './History';

function mapDispatchToProps(dispatch) {
  return {
    getHistory: data => dispatch(request(GET_HISTORY, data)),
  };
}

export default connect(null, mapDispatchToProps)(History);
export { History };
