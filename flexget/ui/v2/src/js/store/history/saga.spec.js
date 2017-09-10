import { stringify } from 'qs';
import { call, put } from 'redux-saga/effects';
import sagaHelper from 'redux-saga-testing';
import { getHistory, defaultOptions } from 'store/history/saga';
import { get } from 'utils/fetch';
import { action } from 'utils/actions';
import { GET_HISTORY } from 'store/history/actions';

describe('store/history/sagas', () => {
  describe('getHistory', () => {
    describe('success', () => {
      const it = sagaHelper(getHistory({ payload: {} }));

      it('should call get /server/history', (result) => {
        expect(result).toEqual(call(get, `/history?${stringify(defaultOptions)}`));

        return { data: { c: 'd' }, headers: { a: 'b' } };
      });

      it('should put the success action', (result) => {
        expect(result).toEqual(put(action(GET_HISTORY, {
          data: { c: 'd' },
          headers: { a: 'b' },
          refresh: true,
        })));
      });
    });

    describe('failure', () => {
      const it = sagaHelper(getHistory({ payload: {} }));

      it('should call get /server/history', (result) => {
        expect(result).toEqual(call(get, `/history?${stringify(defaultOptions)}`));

        return new Error('ERROR');
      });

      it('should put the failure action', (result) => {
        expect(result).toEqual(put(action(GET_HISTORY, new Error('ERROR'))));
      });
    });
  });
});
