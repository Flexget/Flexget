import { LOADING_STATUS, ERROR_STATUS, INFO_STATUS } from '../actions/status';

export default store => next => (action) => {
  if (action.meta && action.meta.loading) {
    return next({
      type: LOADING_STATUS,
      payload: {
        type: action.type,
        namespace: action.meta.namespace,
      },
    });
  } else if (action.error && action.meta && action.payload && !action.meta.ignore) {
    return next({
      type: ERROR_STATUS,
      error: true,
      payload: {
        namespace: action.meta.namespace,
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
        namespace: action.meta.namespace,
      },
    });
    return next(action);
  }
  return next(action);
};
