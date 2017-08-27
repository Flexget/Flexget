import { clearStatus } from 'store/status/actions';

describe('actions/status', () => {
  it('should create an action to close the status', () => {
    expect(clearStatus()).toMatchSnapshot();
  });
});
