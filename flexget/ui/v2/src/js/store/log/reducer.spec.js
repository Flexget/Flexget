import reducer from 'store/log/reducer';
import {
  LOG_CONNECT,
  LOG_MESSAGE,
  LOG_DISCONNECT,
  LOG_CLEAR,
} from 'store/log/actions';

describe('store/log/reducer', () => {
  it('should return the initial state', () => {
    expect(reducer(undefined, {})).toMatchSnapshot();
  });

  it('should be connected on LOG_CONNECT', () => {
    expect(reducer(undefined, { type: LOG_CONNECT }).connected).toBe(true);
  });

  it('should add the messages to the existing messages', () => {
    expect(reducer(undefined, { type: LOG_MESSAGE, payload: ['some messages'] })).toMatchSnapshot();
  });

  it('should be disconnected on LOG_DISCONNECT', () => {
    expect(reducer({ connected: true }, { type: LOG_DISCONNECT }).connected).toBe(false);
  });

  it('should set lines on LOG_CLEAR', () => {
    expect(reducer({ messages: [{ not: 'empty' }] }, { type: LOG_CLEAR }).messages).toHaveLength(0);
  });
});
