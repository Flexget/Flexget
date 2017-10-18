import { connect } from 'react-redux';
import { getGroupedHistory } from 'store/history/selectors';
import HistoryList from './HistoryList';

export function mapStateToProps({ history }, { grouping }) {
  return {
    history: getGroupedHistory(history, grouping),
    hasMore: !history.totalCount || history.items.length < history.totalCount,
  };
}

export default connect(mapStateToProps)(HistoryList);
export { HistoryList };
