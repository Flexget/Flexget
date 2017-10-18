import {
  LOADING_STATUS,
  ERROR_STATUS,
  CLOSE_STATUS,
  INFO_STATUS,
} from 'store/status/actions';
import { LOCATION_CHANGE } from 'connected-react-router';
import reducer from 'store/status/reducer';

const TEST = 'TEST';

describe('store/status/reducer', () => {
  it('should return the initial state', () => {
    expect(reducer(undefined, {})).toEqual({
      loading: {},
      info: null,
      error: null,
    });
  });

  describe('LOADING_STATUS', () => {
    it('should set loading status when initially empty', () => {
      expect(reducer(undefined, {
        type: LOADING_STATUS,
        meta: {
          type: TEST,
        },
      })).toMatchSnapshot();
    });

    it('should set loading status when not empty', () => {
      expect(reducer({
        loading: {
          TEST: true,
        },
        error: null,
        info: null,
      }, {
        type: LOADING_STATUS,
        meta: {
          type: 'OTHER',
        },
      })).toMatchSnapshot();
    });
    it('should not change if already loading that action', () => {
      expect(reducer({
        loading: {
          TEST: true,
        },
        error: null,
        info: null,
      }, {
        type: LOADING_STATUS,
        meta: {
          type: TEST,
        },
      })).toMatchSnapshot();
    });
  });

  it('should handle ERROR_STATUS', () => {
    expect(reducer(undefined, {
      type: ERROR_STATUS,
      payload: {
        message: 'something',
      },
    })).toMatchSnapshot();
  });

  it('should handle INFO_STATUS', () => {
    expect(reducer(undefined, {
      type: INFO_STATUS,
      payload: {
        message: 'something',
      },
    })).toMatchSnapshot();
  });

  it('should clear state on CLOSE_STATUS', () => {
    expect(reducer(undefined, { type: CLOSE_STATUS })).toMatchSnapshot();
  });

  it('should clear state on LOCATION_CHANGE', () => {
    expect(reducer(undefined, { type: LOCATION_CHANGE })).toMatchSnapshot();
  });

  it('should handle loding done', () => {
    expect(reducer({
      loading: {
        TEST: true,
      },
      error: null,
      info: null,
    }, {
      type: TEST,
    })).toMatchSnapshot();
  });
});
