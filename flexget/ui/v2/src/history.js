import createHistory from 'history/createBrowserHistory';

export default createHistory({
  basename: process.env.NODE_ENV === 'production' ? '/v2/' : '',
});
