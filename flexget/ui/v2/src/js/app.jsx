import React from 'react';
import ReactDOM from 'react-dom';
import Root from 'routes';
import 'normalize.css';

ReactDOM.render(<Root />, document.getElementById('react'));

if (module.hot) {
  module.hot.accept('./routes', () => {
    const NewRoot = require('./routes').default; // eslint-disable-line global-require
    ReactDOM.render(<NewRoot />, document.getElementById('react'));
  });
}
