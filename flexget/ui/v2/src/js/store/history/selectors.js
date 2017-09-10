import { createSelector } from 'reselect';
import { groupBy } from 'utils/array';

const getItems = history => history.items;
const getGrouping = (history, grouping) => grouping;
const historyGroupBy = (items, grouping, transform) => groupBy(items, grouping, transform);
const getHistoryGroupedByTime = createSelector(
  [getItems, getGrouping],
  (items, grouping) => historyGroupBy(items, grouping, i => i.split('T')[0]),
);
const getHistoryGroupedByTask = createSelector(
  [getItems, getGrouping],
  historyGroupBy,
);

export const getGroupedHistory = (history, grouping) => (
  grouping === 'time' ?
    getHistoryGroupedByTime :
    getHistoryGroupedByTask
)(history, grouping);
