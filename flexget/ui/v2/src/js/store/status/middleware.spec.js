import configureMockStore from 'redux-mock-store';
import statusMiddleware from 'store/status/middleware';
import { action, request } from 'utils/actions';

const ACTION = 'ACTION';
const mockStore = configureMockStore([statusMiddleware]);
const store = mockStore({});

describe('store/status/middleware', () => {
  afterEach(() => store.clearActions());

  it('should dispatch LOADING_STATUS if loading', () => {
    store.dispatch(request(ACTION));
    expect(store.getActions()).toMatchSnapshot();
  });


  it('should dispatch ERROR_STATUS if error and not ignore', () => {
    const err = new Error('Unauthorized');
    err.status = 401;

    store.dispatch(action(ACTION, err));
    expect(store.getActions()).toMatchSnapshot();
  });

  it('should not dispatch ERROR_STATUS if error and ignore', () => {
    const err = new Error('Unauthorized');
    err.status = 401;
    store.dispatch(action(ACTION, err, { ignore: true }));

    expect(store.getActions()).toMatchSnapshot();
  });

  it('should dispatch INFO_STATUS and the original action if message is set', () => {
    store.dispatch(action(ACTION, {}, { message: 'A message' }));
    expect(store.getActions()).toMatchSnapshot();
  });
});
