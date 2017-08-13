import { createStore, applyMiddleware, compose } from 'redux';
import createSagaMiddleware from 'redux-saga';
import { connectRouter, routerMiddleware } from 'connected-react-router';
import history from 'history';
import reducer from 'reducers';
import status from 'middleware/status';
import rootSaga from 'sagas';

export default () => {
  const sagaMiddleware = createSagaMiddleware();
  const store = createStore(
    connectRouter(history)(reducer),
    compose(
      applyMiddleware(
        status,
        routerMiddleware(history),
        sagaMiddleware,
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

  sagaMiddleware.run(rootSaga);

  return store;
};
