import * as utils from 'utils/actions';
import { post } from 'utils/fetch';

export const SERVER = 'SERVER';
export const SERVER_RELOAD = 'SERVER_RELOAD';
export const SERVER_SHUTDOWN = 'SERVER_SHUTDOWN';
export const SERVER_RELOAD_DISMISS = 'SERVER_RELOAD_DISMISS';
export const SERVER_SHUTDOWN_PROMPT = 'SERVER_SHUTDOWN_PROMPT';
export const SERVER_SHUTDOWN_PROMPT_DISMISS = 'SERVER_SHUTDOWN_PROMOPT_DISMISS';
export const SERVER_SHUTDOWN_DISMISS = 'SERVER_SHUTDOWN_DISMISS';

const createAction = utils.createAction(SERVER);
const loading = utils.createLoading(SERVER);

function manageServer(action, operation) {
  return (dispatch) => {
    dispatch(loading(action));
    return post('/server/manage', { operation })
      .then(() => dispatch(createAction(action)))
      .catch(err => dispatch(createAction(action, err)));
  };
}

export function reloadServer() {
  return manageServer(SERVER_RELOAD, 'reload');
}

export function shutdownServer() {
  return manageServer(SERVER_SHUTDOWN, 'shutdown');
}

export function dismissReload() {
  return createAction(SERVER_RELOAD_DISMISS);
}

export function showShutdownPrompt() {
  return createAction(SERVER_SHUTDOWN_PROMPT);
}

export function dismissShutdownPrompt() {
  return createAction(SERVER_SHUTDOWN_PROMPT_DISMISS);
}

export function dismissShutdown() {
  return createAction(SERVER_SHUTDOWN_DISMISS);
}
