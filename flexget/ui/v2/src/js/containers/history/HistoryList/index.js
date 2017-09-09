import { connect } from 'react-redux';
import HistoryList from 'components/history/HistoryList';
import { getGroupedHistory } from 'store/history/selector';

function mapStateToProps({ history }, { grouping }) {
  return {
    history: getGroupedHistory(history, grouping),
    hasMore: history.items >= history.totalCount,
  };
}

export default connect(mapStateToProps)(HistoryList);
