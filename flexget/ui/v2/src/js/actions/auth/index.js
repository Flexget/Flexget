import { createAction, loading } from 'utils/actions';
import { get, post } from 'utils/fetch';

const PREFIX = '@flexget/auth/';
export const LOGIN = `${PREFIX}LOGIN`;
export const LOGOUT = `${PREFIX}LOGOUT`;

export function checkLogin() {
  return dispatch => get('/server/version')
      .then(() => dispatch(createAction(LOGIN)))
      .catch(() => {});
}

export function login(credentials) {
  return (dispatch) => {
    dispatch(loading(LOGIN));
    return post('/auth/login', credentials)
      .then(() => dispatch(createAction(LOGIN)))
      .catch(err => dispatch(createAction(LOGIN, err)));
  };
}

export function logout() {
  return (dispatch) => {
    dispatch(loading(LOGOUT));
    return post('/auth/logout')
      .then(() => dispatch(createAction(LOGOUT)))
      .catch(err => dispatch(createAction(LOGOUT, err)));
  };
}
