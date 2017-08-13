import reducer from 'reducers/auth';
import { LOGIN, LOGOUT } from 'actions/auth';
import { ERROR_STATUS } from 'actions/status';
import { GET_VERSION } from 'actions/version';

describe('reducers/auth', () => {
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
