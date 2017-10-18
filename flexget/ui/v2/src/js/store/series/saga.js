import { fork } from 'redux-saga/effects';
import showSaga from 'store/series/shows/saga';

export default function* seriesSaga() {
  yield fork(showSaga);
}
