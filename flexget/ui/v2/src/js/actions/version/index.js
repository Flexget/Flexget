import { createAction, loading } from 'utils/actions';
import { get } from 'utils/fetch';

const PREFIX = '@flexget/version/';
export const GET_VERSION = `${PREFIX}GET_VERSION`;

export function getVersion() {
  return (dispatch) => {
    dispatch(loading(GET_VERSION));
    return get('/server/version')
      .then(({ data }) => dispatch(createAction(GET_VERSION, data)))
      .catch(err => dispatch(createAction(GET_VERSION, err)));
  };
}
