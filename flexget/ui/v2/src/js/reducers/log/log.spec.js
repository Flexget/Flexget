import reducer from 'reducers/log';
import {
  LOG_START,
  LOG_MESSAGE,
  LOG_DISCONNECT,
  LOG_LINES,
  LOG_QUERY,
  LOG_CLEAR,
} from 'actions/log';

describe('reducers/log', () => {
  it('should return the initial state', () => {
    expect(reducer(undefined, {})).toMatchSnapshot();
  });

  it('should be connected on LOG_START', () => {
    expect(reducer(undefined, { type: LOG_START }).connected).toBe(true);
  });

  it('should add the messages to the existing messages', () => {
    expect(reducer(undefined, { type: LOG_MESSAGE, payload: ['some messages'] })).toMatchSnapshot();
  });

  it('should be disconnected on LOG_DISCONNECT', () => {
    expect(reducer({ connected: true }, { type: LOG_DISCONNECT }).connected).toBe(false);
  });

  it('should set lines on LOG_LINES', () => {
    expect(reducer(undefined, { type: LOG_LINES, payload: '200' }).lines).toBe('200');
  });

  it('should set lines on LOG_QUERY', () => {
    expect(reducer(undefined, { type: LOG_QUERY, payload: 'test' }).query).toBe('test');
  });

  it('should set lines on LOG_CLEAR', () => {
    expect(reducer({ messages: [{ not: 'empty' }] }, { type: LOG_CLEAR }).messages).toHaveLength(0);
  });
});
