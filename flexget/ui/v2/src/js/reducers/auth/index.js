import { LOGIN, LOGOUT } from 'actions/auth';
import { ERROR_STATUS } from 'actions/status';

export default function reducer(state = {}, action) {
  switch (action.type) {
    case LOGIN:
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
