import { eventChannel } from 'redux-saga';
import { createMockTask } from 'redux-saga/utils';
import { take, fork, cancel, cancelled, call, put } from 'redux-saga/effects';
import sagaHelper from 'redux-saga-testing';
import { LOG_CONNECT, LOG_DISCONNECT } from 'store/log/actions';
import saga, { log, logStream } from 'store/log/saga';
import { action, requesting } from 'utils/actions';

describe('store/log/saga', () => {
  describe('saga', () => {
    const it = sagaHelper(saga());
    const mockTask = createMockTask();

    it('should take a LOG_CONNECT request', (result) => {
      expect(result.toString()).toEqual(take(requesting(LOG_CONNECT)).toString());

      return { payload: { lines: '200', query: '' } };
    });

    it('should fork the log stream task', (result) => {
      expect(result).toEqual(fork(log, {
        payload: {
          lines: '200',
          query: '',
        },
      }));

      return mockTask;
    });

    it('should take a LOG_DISCONNECT request', (result) => {
      expect(result.toString()).toEqual(take(requesting(LOG_DISCONNECT)).toString());
    });

    it('should cancel the logStreamTask', (result) => {
      expect(result).toEqual(cancel(mockTask));
    });
  });


  describe('log', () => {
    const act = {
      payload: {
        lines: '200',
        query: '',
      },
    };
    const it = sagaHelper(log(act));
    const fn = jest.fn();
    const channel = eventChannel((emit) => {
      emit(action(LOG_CONNECT));

      return () => fn();
    });

    it('should yield a call to the channel', (result) => {
      expect(result).toEqual(call(logStream, act.payload));
      return channel;
    });

    it('should take from the channel', (result) => {
      expect(result).toEqual(take(channel));

      return action(LOG_CONNECT);
    });

    it('should put the action', (result) => {
      expect(result).toEqual(put(action(LOG_CONNECT)));

      return new Error('ERROR');
    });

    it('should check cancelled', (result) => {
      expect(result).toEqual(cancelled());

      return true;
    });

    it('should close the channel and put disconnect', (result) => {
      expect(result).toEqual(put(action(LOG_DISCONNECT)));

      expect(fn).toHaveBeenCalled();
    });
  });
});
