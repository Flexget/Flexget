import reducer from 'reducers/auth';
import { LOGIN, LOGOUT } from 'actions/auth';


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
});
