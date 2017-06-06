import configureMockStore from 'redux-mock-store';
import { LOADING_STATUS, ERROR_STATUS, INFO_STATUS } from 'actions/status';
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
    const expectedActions = [{
      type: LOADING_STATUS,
      payload: {
        type: ACTION,
        namespace: NAMESPACE,
      },
    }];
    store.dispatch(createLoading(ACTION));
    expect(store.getActions()).toEqual(expectedActions);
  });


  it('should dispatch ERROR_STATUS if error and not ignore', () => {
    const expectedActions = [{
      type: ERROR_STATUS,
      error: true,
      payload: {
        type: ACTION,
        namespace: NAMESPACE,
        statusCode: 401,
        message: 'Unauthorized',
      },
    }];
    const err = new Error('Unauthorized');
    err.status = 401;

    store.dispatch(createAction(ACTION, err));
    expect(store.getActions()).toEqual(expectedActions);
  });

  it('should not dispatch ERROR_STATUS if error and ignore', () => {
    const err = new Error('Unauthorized');
    err.status = 401;
    const action = createAction(ACTION, err, { ignore: true });

    const expectedActions = [action];

    store.dispatch(action);
    expect(store.getActions()).toEqual(expectedActions);
  });

  it('should dispatch INFO_STATUS and the original action if message is set', () => {
    const action = createAction(ACTION, {}, { message: 'A message' });
    const expectedActions = [
      {
        type: INFO_STATUS,
        payload: {
          type: ACTION,
          message: 'A message',
          namespace: NAMESPACE,
        },
      },
      action,
    ];

    store.dispatch(action);
    expect(store.getActions()).toEqual(expectedActions);
  });
});
