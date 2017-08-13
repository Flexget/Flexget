import { fork } from 'redux-saga/effects';
import showSaga from 'sagas/series/shows';

export default function* seriesSaga() {
  yield fork(showSaga);
}
