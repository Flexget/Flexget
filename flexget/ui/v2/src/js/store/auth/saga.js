import { call, put, takeLatest } from 'redux-saga/effects';
import { action, requesting } from 'utils/actions';
import { post } from 'utils/fetch';
import { LOGIN, LOGOUT } from 'store/auth/actions';

export function* login({ payload }) {
  try {
    yield call(post, '/auth/login', payload);
    yield put(action(LOGIN));
  } catch (err) {
    yield put(action(LOGIN, err));
  }
}

export function* logout() {
  try {
    yield call(post, '/auth/logout');
    yield put(action(LOGOUT));
  } catch (err) {
    yield put(action(LOGOUT, err));
  }
}

export default function* saga() {
  yield takeLatest(requesting(LOGIN), login);
  yield takeLatest(requesting(LOGOUT), logout);
}
