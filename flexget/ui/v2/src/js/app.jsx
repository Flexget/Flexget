import React from 'react';
import ReactDOM from 'react-dom';
import Root from 'root';
import 'typeface-roboto'; // eslint-disable-line import/extensions
import 'normalize.css';

ReactDOM.render(<Root />, document.getElementById('react'));

if (module.hot) {
  module.hot.accept('./root', () => {
    const NewRoot = require('./root').default; // eslint-disable-line global-require
    ReactDOM.render(<NewRoot />, document.getElementById('react'));
  });
}
