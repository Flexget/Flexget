import {
  LOG_START,
  LOG_MESSAGE,
  LOG_DISCONNECT,
  LOG_LINES,
  LOG_QUERY,
  LOG_CLEAR,
} from 'actions/log';

const initState = {
  messages: [],
  connected: false,
  lines: '200',
  query: '',
};

export default function reducer(state = initState, action) {
  switch (action.type) {
    case LOG_START:
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
    case LOG_LINES:
      return {
        ...state,
        lines: action.payload,
      };
    case LOG_QUERY:
      return {
        ...state,
        query: action.payload,
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
