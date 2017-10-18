import {
  LOG_CONNECT,
  LOG_MESSAGE,
  LOG_DISCONNECT,
  LOG_CLEAR,
} from 'store/log/actions';

const initState = {
  messages: [],
  connected: false,
};

export default function reducer(state = initState, action) {
  switch (action.type) {
    case LOG_CONNECT:
      return {
        ...state,
        messages: [],
        connected: true,
      };
    case LOG_MESSAGE:
      return {
        ...state,
        messages: [action.payload, ...state.messages],
      };
    case LOG_DISCONNECT:
      return {
        ...state,
        connected: false,
      };
    case LOG_CLEAR:
      return {
        ...state,
        messages: [],
      };
    default:
      return state;
  }
}
