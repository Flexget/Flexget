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
  afterEach(() => fetchMock.restore());

  describe('login', () => {
    it('dispatches the correct actions on successful login', () => {
      const store = mockStore({ auth: {} });

      fetchMock
        .post('/api/auth/login', {});

      return store.dispatch(auth.login(credentials))
        .then(() => {
          expect(store.getActions()).toMatchSnapshot();
        });
    });


    it('dispatches the correct actions on unsuccessful login', () => {
      const store = mockStore({ auth: {} });
      fetchMock
        .post('/api/auth/login', { status: 401, body: {} });

      return store.dispatch(auth.login(credentials))
        .then(() => {
          expect(store.getActions()).toMatchSnapshot();
        });
    });
  });

  describe('checkLogin', () => {
    it('dispatches the login action if already logged in', () => {
      const store = mockStore({ auth: {} });

      fetchMock
        .get('/api/server/version', {});

      return store.dispatch(auth.checkLogin())
        .then(() => {
          expect(store.getActions()).toMatchSnapshot();
        });
    });


    it('dispatches no actions if not logged in already', () => {
      const store = mockStore({ auth: {} });
      fetchMock
        .get('/api/server/version', { status: 401, body: {} });

      return store.dispatch(auth.checkLogin())
        .then(() => {
          expect(store.getActions()).toMatchSnapshot();
        });
    });
  });

  describe('logout', () => {
    it('dispatches the correct actions on succesful logout', () => {
      const store = mockStore({ auth: {} });

      fetchMock
        .post('/api/auth/logout', {});

      return store.dispatch(auth.logout())
        .then(() => {
          expect(store.getActions()).toMatchSnapshot();
        });
    });


    it('dispatches the correct actions on unsuccesful logout', () => {
      const store = mockStore({ auth: {} });
      fetchMock
        .post('/api/auth/logout', { status: 401, body: {} });

      return store.dispatch(auth.logout())
        .then(() => {
          expect(store.getActions()).toMatchSnapshot();
        });
    });
  });
});
