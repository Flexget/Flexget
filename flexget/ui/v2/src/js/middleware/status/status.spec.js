import configureMockStore from 'redux-mock-store';
import statusMiddleware from 'middleware/status';
import * as utils from 'utils/actions';

const NAMESPACE = 'TEST';
const ACTION = 'ACTION';
const mockStore = configureMockStore([statusMiddleware]);
const store = mockStore({});
const createLoading = utils.createLoading(NAMESPACE);
const createAction = utils.createAction(NAMESPACE);

describe('middleware/status', () => {
  afterEach(() => store.clearActions());

  it('should dispatch LOADING_STATUS if loading', () => {
    store.dispatch(createLoading(ACTION));
    expect(store.getActions()).toMatchSnapshot();
  });


  it('should dispatch ERROR_STATUS if error and not ignore', () => {
    const err = new Error('Unauthorized');
    err.status = 401;

    store.dispatch(createAction(ACTION, err));
    expect(store.getActions()).toMatchSnapshot();
  });

  it('should not dispatch ERROR_STATUS if error and ignore', () => {
    const err = new Error('Unauthorized');
    err.status = 401;
    const action = createAction(ACTION, err, { ignore: true });

    store.dispatch(action);
    expect(store.getActions()).toMatchSnapshot();
  });

  it('should dispatch INFO_STATUS and the original action if message is set', () => {
    const action = createAction(ACTION, {}, { message: 'A message' });
    store.dispatch(action);
    expect(store.getActions()).toMatchSnapshot();
  });
});
