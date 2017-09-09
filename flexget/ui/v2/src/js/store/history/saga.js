import { stringify } from 'qs';
import { call, put, takeLatest } from 'redux-saga/effects';
import { action, requesting } from 'utils/actions';
import { get } from 'utils/fetch';
import { GET_HISTORY } from 'store/history/actions';

export const defaultOptions = {
  page: 1,
  sort_by: 'time',
  order: 'desc',
};

export function* getHistory({ payload }) {
  const query = { ...defaultOptions, ...payload };
  const refresh = query.page === 1;

  try {
    const { data, headers } = yield call(get, `/history?${stringify(query)}`);
    yield put(action(GET_HISTORY, { data, headers, refresh }));
  } catch (err) {
    yield put(action(GET_HISTORY, err));
  }
}

export default function* saga() {
  yield takeLatest(requesting(GET_HISTORY), getHistory);
}
