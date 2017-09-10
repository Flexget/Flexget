import { connect } from 'react-redux';
import HistoryList from 'components/history/HistoryList';
import { getGroupedHistory } from 'store/history/selectors';

export function mapStateToProps({ history }, { grouping }) {
  return {
    history: getGroupedHistory(history, grouping),
    hasMore: !history.totalCount || history.items.length < history.totalCount,
  };
}

export default connect(mapStateToProps)(HistoryList);
