import { fork } from 'redux-saga/effects';
import authSaga from 'store/auth/saga';
import historySaga from 'store/history/saga';
import logSaga from 'store/log/saga';
import seriesSaga from 'store/series/saga';
import serverSaga from 'store/server/saga';
import versionSaga from 'store/version/saga';

export default function* rootSaga() {
  yield fork(authSaga);
  yield fork(historySaga);
  yield fork(logSaga);
  yield fork(seriesSaga);
  yield fork(serverSaga);
  yield fork(versionSaga);
}
