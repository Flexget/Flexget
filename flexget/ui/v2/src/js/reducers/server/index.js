import {
  SERVER_RELOAD,
  SERVER_SHUTDOWN,
  SERVER_RELOAD_DISMISS,
  SERVER_SHUTDOWN_PROMPT,
  SERVER_SHUTDOWN_PROMPT_DISMISS,
  SERVER_SHUTDOWN_DISMISS,
} from 'actions/server';

const initState = {
  shutdownPrompt: false,
  shutdown: false,
  reload: false,
};

export default function reducer(state = initState, action) {
  switch (action.type) {
    case SERVER_RELOAD:
      return {
        ...state,
        reload: true,
      };
    case SERVER_SHUTDOWN:
      return {
        ...state,
        shutdown: true,
      };
    case SERVER_RELOAD_DISMISS:
      return {
        ...state,
        reload: false,
      };
    case SERVER_SHUTDOWN_PROMPT:
      return {
        ...state,
        shutdownPrompt: true,
      };
    case SERVER_SHUTDOWN_PROMPT_DISMISS:
      return {
        ...state,
        shutdownPrompt: false,
      };
    case SERVER_SHUTDOWN_DISMISS:
      return {
        shutdown: false,
      };
    default:
      return state;
  }
}
