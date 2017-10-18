import { ERROR_STATUS, INFO_STATUS } from 'store/status/actions';

export default store => next => (action) => {
  if (action.error && action.meta && action.payload) {
    return next({
      type: ERROR_STATUS,
      error: true,
      payload: {
        message: action.payload.message,
        statusCode: action.payload.status,
        type: action.type,
      },
    });
  } else if (action.meta && action.meta.message) {
    store.dispatch({
      type: INFO_STATUS,
      payload: {
        type: action.type,
        message: action.meta.message,
      },
    });
  }
  return next(action);
};
