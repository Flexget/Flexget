import * as utils from 'utils/actions';
import { get } from 'utils/fetch';

export const VERSION = 'VERSION';
export const GET_VERSION = 'GET_VERSION';

const createAction = utils.createAction(VERSION);
const loading = utils.createLoading(VERSION);

export function getVersion() {
  return (dispatch) => {
    dispatch(loading(GET_VERSION));
    return get('/server/version')
      .then(version => dispatch(createAction(GET_VERSION, version)))
      .catch(err => dispatch(createAction(GET_VERSION, err)));
  };
}
