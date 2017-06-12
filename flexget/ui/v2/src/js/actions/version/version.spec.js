import fetchMock from 'fetch-mock';
import thunk from 'redux-thunk';
import configureMockStore from 'redux-mock-store';
import { getVersion } from 'actions/version';

const middlewares = [thunk];
const mockStore = configureMockStore(middlewares);
const store = mockStore();

describe('actions/version', () => {
  afterEach(() => {
    fetchMock.restore();
    store.clearActions();
  });

  describe('getVersion', () => {
    it('dispatches the correct actions on successful get version', () => {
      fetchMock
        .get('/api/server/version', {
          api_version: '1.1.2',
          flexget_version: '2.10.11',
          latest_version: '2.10.60',
        });

      return store.dispatch(getVersion())
        .then(() => {
          expect(store.getActions()).toMatchSnapshot();
        });
    });

    it('dispatches the correct actions on unsuccessful get version', () => {
      fetchMock
        .get('/api/server/version', { body: {}, status: 401 });

      return store.dispatch(getVersion())
        .then(() => {
          expect(store.getActions()).toMatchSnapshot();
        });
    });
  });
});
