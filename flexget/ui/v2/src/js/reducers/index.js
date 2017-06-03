import { combineReducers } from 'redux';
import { reducer as form } from 'redux-form';
import auth from 'reducers/auth';
import status from 'reducers/status';

export default combineReducers({
  auth,
  form,
  status,
});
