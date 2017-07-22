import { clearStatus } from 'actions/status';

describe('actions/status', () => {
  it('should create an action to close the status', () => {
    expect(clearStatus()).toMatchSnapshot();
  });
});
