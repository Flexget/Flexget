import { createStore, applyMiddleware, compose } from 'redux';
import createSagaMiddleware from 'redux-saga';
import { connectRouter, routerMiddleware } from 'connected-react-router';
import history from 'history';
import reducer from 'store/reducers';
import status from 'store/status/middleware';
import rootSaga from 'store/sagas';

export default () => {
  const sagaMiddleware = createSagaMiddleware();
  // eslint-disable-next-line no-underscore-dangle
  const composeEnhancers = window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__ || compose;
  const store = createStore(
    connectRouter(history)(reducer),
    composeEnhancers(
      applyMiddleware(
        status,
        routerMiddleware(history),
        sagaMiddleware,
      ),
    ),
  );

  if (module.hot) {
    module.hot.accept('store/reducers', () => {
      const nextReducer = require('store/reducers').default; // eslint-disable-line global-require
      store.replaceReducer(nextReducer);
    });
  }

  sagaMiddleware.run(rootSaga);

  return store;
};
