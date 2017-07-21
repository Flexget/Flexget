import * as utils from 'utils/actions';
import { post } from 'utils/fetch';

export const SERVER = 'SERVER';
export const SERVER_RELOAD = 'SERVER_RELOAD';
export const SERVER_SHUTDOWN = 'SERVER_SHUTDOWN';

const createAction = utils.createAction(SERVER);
const loading = utils.createLoading(SERVER);

function manageServer(action, operation) {
  return (dispatch) => {
    dispatch(loading(action));
    return post('/server/manage', { operation })
      .then(({ message }) => dispatch(createAction(action, {}, { message })))
      .catch(err => dispatch(createAction(action, err)));
  };
}

export function reloadServer() {
  return manageServer(SERVER_RELOAD, 'reload');
}

export function shutdownServer() {
  return manageServer(SERVER_SHUTDOWN, 'shutdown');
}
