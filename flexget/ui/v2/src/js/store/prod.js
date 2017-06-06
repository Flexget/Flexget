import { createStore, applyMiddleware, compose } from 'redux';
import { connectRouter, routerMiddleware } from 'connected-react-router';
import history from 'history';
import thunk from 'redux-thunk';
import reducer from 'reducers';
import status from 'middleware/status';

const store = createStore(
  connectRouter(history)(reducer),
  compose(
    applyMiddleware(
      thunk,
      status,
      routerMiddleware(history),
    ),
  ),
);

export default store;
