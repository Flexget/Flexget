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
    ),
  );

  sagaMiddleware.run(rootSaga);

  return store;
};
