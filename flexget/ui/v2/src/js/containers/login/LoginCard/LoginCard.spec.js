import { mapStateToProps } from 'containers/login/LoginCard';

describe('containers/login/LoginCard', () => {
  it('should return no errors if there are none', () => {
    expect(mapStateToProps({ status: { } })).toMatchSnapshot();
  });

  it('should return errors if there are errors', () => {
    expect(mapStateToProps({ status: { error: { message: 'Invalid Credentials' } } })).toMatchSnapshot();
  });
});
