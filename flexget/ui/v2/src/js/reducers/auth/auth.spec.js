import reducer from 'reducers/auth';
import { LOGIN, LOGOUT } from 'actions/auth';
import { ERROR_STATUS } from 'actions/status';

describe('reducers/auth', () => {
  it('should return the initial state', () => {
    expect(reducer(undefined, {})).toEqual({});
  });

  it('should handle LOGIN', () => {
    expect(reducer(undefined, { type: LOGIN })).toEqual({ loggedIn: true });
  });

  it('should handle LOGOUT', () => {
    expect(reducer({ loggedIn: true }, { type: LOGOUT })).toEqual({});
  });

  it('should handle a 401 ERROR_STATUS', () => {
    expect(reducer({ loggedIn: true }, {
      type: ERROR_STATUS,
      payload: {
        statusCode: 401,
      },
    })).toEqual({});
  });

  it('should handle a non 401 ERROR_STATUS', () => {
    expect(reducer({ loggedIn: true }, {
      type: ERROR_STATUS,
      payload: {
        statusCode: 404,
      },
    })).toEqual({ loggedIn: true });
  });
});
