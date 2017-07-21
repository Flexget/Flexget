import fetchMock from 'fetch-mock';
import thunk from 'redux-thunk';
import configureMockStore from 'redux-mock-store';
import {
  reloadServer,
  shutdownServer,
  dismissReload,
  showShutdownPrompt,
  dismissShutdownPrompt,
  dismissShutdown,
} from 'actions/server';

const middlewares = [thunk];
const mockStore = configureMockStore(middlewares);
const store = mockStore();

describe('actions/server', () => {
  afterEach(() => {
    fetchMock.restore();
    store.clearActions();
  });

  describe('reloadServer', () => {
    it('dispatches the correct action on successful server reload', () => {
      fetchMock
        .post('/api/server/manage', 200);

      return store.dispatch(reloadServer())
        .then(() => {
          expect(store.getActions()).toMatchSnapshot();
        });
    });

    it('dispatches the correct action on unsuccessful server reload', () => {
      fetchMock
        .post('/api/server/manage', { body: { message: 'error' }, status: 500 });

      return store.dispatch(reloadServer())
        .then(() => {
          expect(store.getActions()).toMatchSnapshot();
        });
    });
  });

  describe('shutdownServer', () => {
    it('dispatches the correct action on successful server shutdown', () => {
      fetchMock
        .post('/api/server/manage', 200);

      return store.dispatch(shutdownServer())
        .then(() => {
          expect(store.getActions()).toMatchSnapshot();
        });
    });

    it('dispatches the correct action on unsuccessful server shutdown', () => {
      fetchMock
        .post('/api/server/manage', { body: { message: 'error' }, status: 500 });

      return store.dispatch(shutdownServer())
        .then(() => {
          expect(store.getActions()).toMatchSnapshot();
        });
    });
  });
});
