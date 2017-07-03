import { mapStateToProps } from 'containers/log/Header';

describe('containers/log/Header', () => {
  it('should return the right stuff', () => {
    expect(mapStateToProps({ log: {
      connected: true,
      lines: 400,
      query: 'query',
    } })).toMatchSnapshot();
  });
});
