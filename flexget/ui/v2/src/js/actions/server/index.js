import { createAction, loading } from 'utils/actions';
import { post } from 'utils/fetch';

const PREFIX = '@flexget/server/';
export const SERVER_RELOAD = `${PREFIX}SERVER_RELOAD`;
export const SERVER_SHUTDOWN = `${PREFIX}SERVER_SHUTDOWN`;


function manageServer(action, operation) {
  return (dispatch) => {
    dispatch(loading(action));
    return post('/server/manage', { operation })
      .then(({ data }) => dispatch(createAction(action, {}, { message: data.message })))
      .catch(err => dispatch(createAction(action, err)));
  };
}

export function reloadServer() {
  return manageServer(SERVER_RELOAD, 'reload');
}

export function shutdownServer() {
  return manageServer(SERVER_SHUTDOWN, 'shutdown');
}
