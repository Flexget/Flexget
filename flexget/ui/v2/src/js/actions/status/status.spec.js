import { closeStatus } from 'actions/status';

describe('actions/status', () => {
  it('should create an action to close the status', () => {
    expect(closeStatus()).toMatchSnapshot();
  });
});
