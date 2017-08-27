import { GET_VERSION } from 'store/version/actions';

export default function reducer(state = {}, action) {
  switch (action.type) {
    case GET_VERSION: {
      const {
        api_version: api,
        flexget_version: flexget,
        latest_version: latest,
      } = action.payload;

      return { api, flexget, latest };
    }
    default:
      return state;
  }
}
