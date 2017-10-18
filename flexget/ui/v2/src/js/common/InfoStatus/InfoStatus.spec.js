import { mapStateToProps } from 'common/InfoStatus';

describe('plugins/common/InfoStatus', () => {
  it('should be correct if an info status should be displayed', () => {
    expect(mapStateToProps({ status: { info: 'Info Status' } })).toMatchSnapshot();
  });

  it('should be correct if an info status should not be displayed', () => {
    expect(mapStateToProps({ status: { } })).toMatchSnapshot();
  });
});
