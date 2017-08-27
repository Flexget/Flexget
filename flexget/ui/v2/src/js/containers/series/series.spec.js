import { mapStateToProps } from 'containers/series';

describe('containers/series', () => {
  it('should return the right stuff', () => {
    expect(mapStateToProps({ series: {
      shows: {
        items: [],
      },
    } })).toMatchSnapshot();
  });
});
