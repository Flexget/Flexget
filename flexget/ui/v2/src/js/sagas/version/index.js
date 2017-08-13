import { call, put, takeLatest } from 'redux-saga/effects';
import { action, requesting } from 'utils/actions';
import { get } from 'utils/fetch';
import { GET_VERSION } from 'actions/version';

export function* getVersion() {
  try {
    const { data } = yield call(get, '/server/version');
    yield put(action(GET_VERSION, data));
  } catch (err) {
    yield put(action(GET_VERSION, err));
  }
}

export default function* saga() {
  yield takeLatest(requesting(GET_VERSION), getVersion);
}
