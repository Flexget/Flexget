import oboe from 'oboe';
import * as utils from 'utils/actions';

export const LOG = 'LOG';
export const LOG_START = 'LOG_START';
export const LOG_MESSAGE = 'LOG_MESSAGE';
export const LOG_DISCONNECT = 'LOG_DISCONNECT';
export const LOG_LINES = 'LOG_LINES';
export const LOG_QUERY = 'LOG_QUERY';
export const LOG_CLEAR = 'LOG_CLEAR';

const createAction = utils.createAction(LOG);

export function startLogStream() {
  return (dispatch, getState) => {
    const { lines, query } = getState().log;
    const stream = oboe({
      url: `api/server/log?lines=${lines}&search=${query}`,
      method: 'GET',
    });

    const promise = new Promise((resolve, reject) => {
      stream
        .on('start', () => dispatch(createAction(LOG_START)))
        .on('node', '{message}', message => dispatch(createAction(LOG_MESSAGE, message)))
        .done(() => resolve())
        .fail(err => reject(err));
    });

    promise.abort = () => {
      stream.abort();
      dispatch(createAction(LOG_DISCONNECT));
    };

    return promise;
  };
}

export function setLines(lines) {
  return createAction(LOG_LINES, lines);
}

export function setQuery(query) {
  return createAction(LOG_QUERY, query);
}

export function clearLogs() {
  return createAction(LOG_CLEAR);
}
