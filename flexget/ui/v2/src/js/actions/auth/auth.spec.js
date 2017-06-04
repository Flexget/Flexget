import fetchMock from 'fetch-mock';
import thunk from 'redux-thunk';
import configureMockStore from 'redux-mock-store';
import * as auth from 'actions/auth';

const middlewares = [thunk];
const mockStore = configureMockStore(middlewares);
const credentials = {
  username: 'flexget',
  password: 'test',
};

describe('actions/auth', () => {
  afterEach(() => {
    fetchMock.restore();
  });

  describe('login', () => {
    it('dispatches the correct actions on succesful login', () => {
      const expectedActions = [
        expect.objectContaining({
          type: auth.LOGIN,
          meta: {
            namespace: auth.AUTH,
            loading: true,
          },
        }),
        expect.objectContaining({
          type: auth.LOGIN,
          error: false,
        }),
      ];
      const store = mockStore({ auth: {} });

      fetchMock
        .post('/api/auth/login', {});

      return store.dispatch(auth.login(credentials))
        .then(() => {
          expect(store.getActions()).toEqual(expectedActions);
        });
    });


    it('dispatches the correct actions on unsuccesful login', () => {
      const expectedActions = [
        expect.objectContaining({
          type: auth.LOGIN,
          meta: {
            namespace: auth.AUTH,
            loading: true,
          },
        }),
        expect.objectContaining({
          type: auth.LOGIN,
          error: true,
        }),
      ];
      const store = mockStore({ auth: {} });
      fetchMock
        .post('/api/auth/login', 401);

      return store.dispatch(auth.login(credentials))
        .then(() => {
          expect(store.getActions()).toEqual(expectedActions);
        });
    });
  });

  describe('checkLogin', () => {
    it('dispatches the login action if already logged in', () => {
      const expectedActions = [
        expect.objectContaining({
          type: auth.LOGIN,
          error: false,
        }),
      ];
      const store = mockStore({ auth: {} });

      fetchMock
        .get('/api/server/version', {});

      return store.dispatch(auth.checkLogin())
        .then(() => {
          expect(store.getActions()).toEqual(expectedActions);
        });
    });


    it('dispatches no actions if not logged in already', () => {
      const expectedActions = [];
      const store = mockStore({ auth: {} });
      fetchMock
        .get('/api/server/version', 401);

      return store.dispatch(auth.checkLogin())
        .then(() => {
          expect(store.getActions()).toEqual(expectedActions);
        });
    });
  });

  describe('logout', () => {
    it('dispatches the correct actions on succesful logout', () => {
      const expectedActions = [
        expect.objectContaining({
          type: auth.LOGOUT,
          meta: {
            namespace: auth.AUTH,
            loading: true,
          },
        }),
        expect.objectContaining({
          type: auth.LOGOUT,
          error: false,
        }),
      ];
      const store = mockStore({ auth: {} });

      fetchMock
        .get('/api/auth/logout', {});

      return store.dispatch(auth.logout())
        .then(() => {
          expect(store.getActions()).toEqual(expectedActions);
        });
    });


    it('dispatches the correct actions on unsuccesful logout', () => {
      const expectedActions = [
        expect.objectContaining({
          type: auth.LOGOUT,
          meta: {
            namespace: auth.AUTH,
            loading: true,
          },
        }),
        expect.objectContaining({
          type: auth.LOGOUT,
          error: true,
        }),
      ];
      const store = mockStore({ auth: {} });
      fetchMock
        .get('/api/auth/logout', 401);

      return store.dispatch(auth.logout())
        .then(() => {
          expect(store.getActions()).toEqual(expectedActions);
        });
    });
  });
});
