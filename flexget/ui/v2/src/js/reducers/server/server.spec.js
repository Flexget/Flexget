import reducer from 'reducers/server';
import {
  SERVER_RELOAD,
  SERVER_SHUTDOWN,
  SERVER_RELOAD_DISMISS,
  SERVER_SHUTDOWN_PROMPT,
  SERVER_SHUTDOWN_PROMPT_DISMISS,
  SERVER_SHUTDOWN_DISMISS,
} from 'actions/server';

describe('reducers/server', () => {
  it('should return the initial state', () => {
    expect(reducer(undefined, {})).toMatchSnapshot();
  });

  it('reload should be true on SERVER_RELOAD', () => {
    expect(reducer(undefined, { type: SERVER_RELOAD }).reload).toBe(true);
  });

  it('reload should be true on SERVER_RELOAD_DISMISS', () => {
    expect(reducer(undefined, { type: SERVER_RELOAD_DISMISS }).reload).toBe(false);
  });

  it('reload should be true on SERVER_SHUTDOWN', () => {
    expect(reducer(undefined, { type: SERVER_SHUTDOWN }).shutdown).toBe(true);
  });

  it('reload should be true on SERVER_SHUTDOWN_DISMISS', () => {
    expect(reducer(undefined, { type: SERVER_SHUTDOWN_DISMISS }).shutdown).toBe(false);
  });

  it('reload should be true on SERVER_SHUTDOWN_PROMPT', () => {
    expect(reducer(undefined, { type: SERVER_SHUTDOWN_PROMPT }).shutdownPrompt).toBe(true);
  });

  it('reload should be true on SERVER_SHUTDOWN_DISMISS', () => {
    expect(reducer(undefined, { type: SERVER_SHUTDOWN_PROMPT_DISMISS }).shutdownPrompt).toBe(false);
  });
});
