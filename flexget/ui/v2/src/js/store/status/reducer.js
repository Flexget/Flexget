import {
  LOADING_STATUS,
  ERROR_STATUS,
  CLOSE_STATUS,
  INFO_STATUS,
} from 'store/status/actions';
import { LOCATION_CHANGE } from 'connected-react-router';

const initState = {
  loading: {},
  info: null,
  error: null,
};

export default (state = initState, action) => {
  switch (action.type) {
    case LOADING_STATUS:
      return {
        ...state,
        loading: {
          ...state.loading,
          [action.meta.type]: true,
        },
      };
    case ERROR_STATUS: {
      const {
        [action.payload.type]: omit,
        ...loading
      } = state.loading;
      return {
        ...state,
        error: action.payload,
        loading,
      };
    }
    case INFO_STATUS:
      return {
        ...state,
        info: action.payload.message,
      };
    case CLOSE_STATUS:
    case LOCATION_CHANGE:
      return {
        ...initState,
        loading: state.loading,
      };
    default:
      if (state.loading[action.type]) {
        const {
          [action.type]: omit,
          ...loading
        } = state.loading;
        return {
          ...state,
          loading,
        };
      }
      return state;
  }
};
