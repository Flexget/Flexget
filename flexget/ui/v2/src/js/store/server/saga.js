import { call, put, takeEvery } from 'redux-saga/effects';
import { action, requesting } from 'utils/actions';
import { post } from 'utils/fetch';
import { SERVER_RELOAD, SERVER_SHUTDOWN } from 'store/server/actions';

export function* manageServer(operation, { meta }) {
  try {
    const { data } = yield call(post, '/server/manage', { operation });
    yield put(action(meta.type, {}, { message: data.message }));
  } catch (err) {
    yield put(action(meta.type, err));
  }
}

export default function* saga() {
  yield takeEvery(requesting(SERVER_RELOAD), manageServer, 'reload');
  yield takeEvery(requesting(SERVER_SHUTDOWN), manageServer, 'shutdown');
}
