import reducer from 'store/auth/reducer';

import { LOGIN, LOGOUT } from 'store/auth/actions';
import { ERROR_STATUS } from 'store/status/actions';
import { GET_VERSION } from 'store/version/actions';

describe('store/auth/reducer', () => {
  it('should return the initial state', () => {
    expect(reducer(undefined, {})).toMatchSnapshot();
  });

  it('should login on LOGIN', () => {
    expect(reducer(undefined, { type: LOGIN })).toMatchSnapshot();
  });

  it('should login on GET_VERSION', () => {
    expect(reducer(undefined, { type: GET_VERSION })).toMatchSnapshot();
  });

  it('should logout on LOGOUT', () => {
    expect(reducer({ loggedIn: true }, { type: LOGOUT })).toMatchSnapshot();
  });

  it('should logout on a 401 ERROR_STATUS', () => {
    expect(reducer({ loggedIn: true }, {
      type: ERROR_STATUS,
      payload: {
        statusCode: 401,
      },
    })).toMatchSnapshot();
  });

  it('should stay logged In on a non 401 ERROR_STATUS', () => {
    expect(reducer({ loggedIn: true }, {
      type: ERROR_STATUS,
      payload: {
        statusCode: 404,
      },
    })).toMatchSnapshot();
  });
});
