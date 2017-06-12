import { mapStateToProps } from 'containers/layout/Version';

describe('containers/layout/Version', () => {
  it('should return the version', () => {
    expect(mapStateToProps({ version: {
      api: '1.1.2',
      flexget: '2.10.11',
      latest: '2.10.60',
    } })).toMatchSnapshot();
  });
});
