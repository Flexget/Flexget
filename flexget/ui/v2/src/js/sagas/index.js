import { fork } from 'redux-saga/effects';
import authSaga from 'sagas/auth';
import logSaga from 'sagas/log';
import seriesSaga from 'sagas/series';
import serverSaga from 'sagas/server';
import versionSaga from 'sagas/version';

export default function* rootSaga() {
  yield fork(authSaga);
  yield fork(logSaga);
  yield fork(seriesSaga);
  yield fork(serverSaga);
  yield fork(versionSaga);
}
