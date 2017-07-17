import configureMockStore from 'redux-mock-store';
import * as log from 'actions/log';

const mockStore = configureMockStore();

describe('actions/log', () => {
  describe('setLines', () => {
    it('dispatches the correct acction when setting lines', () => {
      const store = mockStore({ log: {} });

      store.dispatch(log.setLines(400));
      expect(store.getActions()).toMatchSnapshot();
    });
  });

  describe('setQuery', () => {
    it('dispatches the correct acction when setting query', () => {
      const store = mockStore({ log: {} });

      store.dispatch(log.setQuery(400));
      expect(store.getActions()).toMatchSnapshot();
    });
  });

  describe('clearLogs', () => {
    it('dispatches the correct acction when clearing logs', () => {
      const store = mockStore({ log: {} });

      store.dispatch(log.clearLogs(400));
      expect(store.getActions()).toMatchSnapshot();
    });
  });
});
