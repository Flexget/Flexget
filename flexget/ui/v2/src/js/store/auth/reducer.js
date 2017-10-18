import { LOGIN, LOGOUT } from 'store/auth/actions';
import { ERROR_STATUS } from 'store/status/actions';
import { GET_VERSION } from 'store/version/actions';

export default function reducer(state = {}, action) {
  switch (action.type) {
    case LOGIN:
    case GET_VERSION:
      return {
        loggedIn: true,
      };
    case LOGOUT:
      return {};
    case ERROR_STATUS:
      if (action.payload.statusCode === 401) {
        return {};
      }
    default: // eslint-disable-line no-fallthrough
      return state;
  }
}
