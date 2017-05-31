import { createStore, applyMiddleware, compose } from 'redux';
import { connectRouter, routerMiddleware } from 'connected-react-router';
import history from 'history';
import thunk from 'redux-thunk';
import reducer from 'reducers';

const store = createStore(
  connectRouter(history)(reducer),
  compose(
    applyMiddleware(
      thunk,
      routerMiddleware(history),
    ),
    window.devToolsExtension ? window.devToolsExtension() : f => f,
  ),
);

if (module.hot) {
  module.hot.accept('../reducers', () => {
    const nextReducer = require('../reducers').default; // eslint-disable-line global-require
    store.replaceReducer(nextReducer);
  });
}
export default store;
