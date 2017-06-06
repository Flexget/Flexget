import {
  LOADING_STATUS,
  ERROR_STATUS,
  CLOSE_STATUS,
  INFO_STATUS,
} from 'actions/status';
import { LOCATION_CHANGE } from 'connected-react-router';
import reducer from 'reducers/status';

const TEST = 'TEST';
const NAMESPACE = 'NAMESPACE';

describe('reducers/status', () => {
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
        payload: {
          type: TEST,
          namespace: NAMESPACE,
        },
      })).toEqual({
        loading: {
          TEST: NAMESPACE,
        },
        error: null,
        info: null,
      });
    });

    it('should set loading status when not empty', () => {
      expect(reducer({
        loading: {
          TEST: NAMESPACE,
        },
        error: null,
        info: null,
      }, {
        type: LOADING_STATUS,
        payload: {
          type: 'OTHER',
          namespace: NAMESPACE,
        },
      })).toEqual({
        loading: {
          TEST: NAMESPACE,
          OTHER: NAMESPACE,
        },
        error: null,
        info: null,
      });
    });
    it('should not change if already loading that action', () => {
      expect(reducer({
        loading: {
          TEST: NAMESPACE,
        },
        error: null,
        info: null,
      }, {
        type: LOADING_STATUS,
        payload: {
          type: TEST,
          namespace: NAMESPACE,
        },
      })).toEqual({
        loading: {
          TEST: NAMESPACE,
        },
        error: null,
        info: null,
      });
    });
  });

  it('should handle ERROR_STATUS', () => {
    expect(reducer(undefined, {
      type: ERROR_STATUS,
      payload: {
        message: 'something',
      },
    })).toEqual({
      loading: {},
      error: {
        message: 'something',
      },
      info: null,
    });
  });

  it('should handle INFO_STATUS', () => {
    expect(reducer(undefined, {
      type: INFO_STATUS,
      payload: {
        message: 'something',
      },
    })).toEqual({
      loading: {},
      error: null,
      info: 'something',
    });
  });

  it('should handle CLOSE_STATUS', () => {
    expect(reducer(undefined, { type: CLOSE_STATUS })).toEqual({
      loading: {},
      error: null,
      info: null,
    });
  });

  it('should handle LOCATION_CHANGE', () => {
    expect(reducer(undefined, { type: LOCATION_CHANGE })).toEqual({
      loading: {},
      error: null,
      info: null,
    });
  });

  it('should handle loding done', () => {
    expect(reducer({
      loading: {
        TEST: NAMESPACE,
      },
      error: null,
      info: null,
    }, {
      type: TEST,
    })).toEqual({
      loading: {},
      error: null,
      info: null,
    });
  });
});
