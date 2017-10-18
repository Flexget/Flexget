import reducer from 'store/history/reducer';
import { GET_HISTORY } from 'store/history/actions';
import { Headers } from 'utils/tests';


describe('store/history/reducer', () => {
  it('should return the initial state', () => {
    expect(reducer(undefined, {})).toMatchSnapshot();
  });

  it('should store history on GET_HISTORY', () => {
    expect(reducer(undefined, {
      type: GET_HISTORY,
      payload: {
        data: [{ an: 'object' }],
        headers: new Headers({ 'total-count': 1 }),
      },
    })).toMatchSnapshot();
  });
});
