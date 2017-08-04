import qs from 'qs';
import { createAction, loading } from 'utils/actions';
import { get } from 'utils/fetch';

const PREFIX = '@flexget/series/shows/';
export const GET_SERIES = `${PREFIX}GET_SHOWS`;
export const CREATE_SERIES = `${PREFIX}CREATE_SHOWS`;

export function getSeries(options) {
  const defaultOptions = {
    per_page: 10,
    lookup: 'tvdb',
    order: 'asc',
    sort_by: 'show_name',
  };
  const query = { ...options, ...defaultOptions };

  return (dispatch) => {
    dispatch(loading(GET_SERIES));
    return get(`/series?${qs.stringify(query)}`)
      .then(({ data, headers }) => dispatch(createAction(GET_SERIES, { data, headers })))
      .catch(err => dispatch(createAction(GET_SERIES, err)));
  };
}
