import oboe from 'oboe';
import { eventChannel } from 'redux-saga';
import { call, take, put, cancel, cancelled, fork } from 'redux-saga/effects';
import { action, requesting } from 'utils/actions';
import {
  LOG_CONNECT,
  LOG_MESSAGE,
  LOG_DISCONNECT,
} from 'store/log/actions';

export function logStream({ lines, query }) {
  return eventChannel((emit) => {
    const stream = oboe({
      url: `api/server/log?lines=${lines}&search=${query}`,
      method: 'GET',
    });

    stream
      .start(() => emit(action(LOG_CONNECT)))
      .node('{message task}', message => emit(action(LOG_MESSAGE, message)))
      .fail(err => err.jsonBody && emit(action(LOG_MESSAGE, new Error(err.jsonBody.message))));

    return () => stream.abort();
  });
}

export function* log({ payload }) {
  const chan = yield call(logStream, payload);

  try {
    while (true) {
      const logAction = yield take(chan);
      yield put(logAction);
    }
  } finally {
    if (yield cancelled()) {
      chan.close();
      yield put(action(LOG_DISCONNECT));
    }
  }
}

export default function* saga() {
  while (true) {
    const connectAction = yield take(requesting(LOG_CONNECT));
    const logStreamTask = yield fork(log, connectAction);

    yield take(requesting(LOG_DISCONNECT));

    yield cancel(logStreamTask);
  }
}
