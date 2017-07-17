import { mapStateToProps } from 'containers/log/LogTable';

describe('containers/log/LogTable', () => {
  it('should return the right stuff', () => {
    expect(mapStateToProps({ log: {
      messages: [],
    } })).toMatchSnapshot();
  });
});
