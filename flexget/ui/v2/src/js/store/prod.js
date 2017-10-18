import { createStore, applyMiddleware, compose } from 'redux';
import createSagaMiddleware from 'redux-saga';
import { connectRouter, routerMiddleware } from 'connected-react-router';
import history from 'history';
import reducer from 'store/reducers';
import status from 'store/status/middleware';
import rootSaga from 'store/sagas';

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
    ),
  );

  sagaMiddleware.run(rootSaga);

  return store;
};
