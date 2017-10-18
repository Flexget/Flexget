import { clearStatus } from 'store/status/actions';

describe('store/status/actions', () => {
  it('should create an action to close the status', () => {
    expect(clearStatus()).toMatchSnapshot();
  });
});
