import { LOGIN, LOGOUT } from 'actions/auth';

export default function reducer(state = {}, action) {
  switch (action.type) {
    case LOGIN:
      return {
        loggedIn: true,
      };
    case LOGOUT:
      return {};
    default:
      if (action.error && action.payload && action.payload.status === 401) {
        return {};
      }

      return state;
  }
}
