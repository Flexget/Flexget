import { LOGIN, LOGOUT } from 'actions/auth';
import { ERROR_STATUS } from 'actions/status';
import { GET_VERSION } from 'actions/version';

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
