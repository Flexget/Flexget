import { stringify } from 'qs';
import { delay } from 'redux-saga';
import { call, put, takeLatest } from 'redux-saga/effects';
import { action, requesting } from 'utils/actions';
import { get } from 'utils/fetch';
import { GET_SHOWS } from 'store/series/shows/actions';

export const defaultOptions = {
  per_page: 10,
  lookup: 'tvdb',
  order: 'asc',
  sort_by: 'show_name',
};

export function* getShows({ payload } = {}) {
  const query = { ...defaultOptions, ...payload };

  yield call(delay, 500);

  try {
    const { data, headers } = yield call(get, `/series?${stringify(query)}`);
    yield put(action(GET_SHOWS, { data, headers }));
  } catch (err) {
    yield put(action(GET_SHOWS, err));
  }
}

export default function* saga() {
  yield takeLatest(requesting(GET_SHOWS), getShows);
}
