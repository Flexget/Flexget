import { closeStatus, CLOSE_STATUS } from 'actions/status';

describe('actions/status', () => {
  it('should create an action to close the status', () => {
    const expectedAction = {
      type: CLOSE_STATUS,
    };
    expect(closeStatus()).toEqual(expectedAction);
  });
});
