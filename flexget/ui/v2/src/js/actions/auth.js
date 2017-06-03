import * as utils from 'utils/actions';
import { get, post } from 'utils/fetch';

export const AUTH = 'AUTH';
export const LOGIN = 'LOGIN';
export const LOGOUT = 'LOGOUT';

const createAction = utils.createAction(AUTH);
const loading = utils.createLoading(AUTH);

export function checkLogin() {
  return (dispatch) => {
    get('/server/version')
      .then(() => dispatch(createAction(LOGIN)))
      .catch(() => {});
  };
}

export function login(credentials) {
  return (dispatch) => {
    dispatch(loading(LOGIN));
    post('/auth/login', credentials)
      .then(() => dispatch(createAction(LOGIN)))
      .catch(err => dispatch(createAction(LOGIN, err)));
  };
}

export function logout() {
  return (dispatch) => {
    dispatch(loading(LOGOUT));
    get('/auth/logout')
      .then(() => dispatch(createAction(LOGOUT)))
      .then(err => dispatch(createAction(LOGOUT, err)));
  };
}
