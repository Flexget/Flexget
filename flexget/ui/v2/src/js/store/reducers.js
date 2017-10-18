import { combineReducers } from 'redux';
import { reducer as form } from 'redux-form';
import auth from 'store/auth/reducer';
import history from 'store/history/reducer';
import log from 'store/log/reducer';
import series from 'store/series/reducer';
import status from 'store/status/reducer';
import version from 'store/version/reducer';

export default combineReducers({
  auth,
  form,
  history,
  log,
  series,
  status,
  version,
});
