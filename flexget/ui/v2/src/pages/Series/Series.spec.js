import { mapStateToProps } from './index';

describe('containers/series', () => {
  it('should return the right stuff', () => {
    expect(mapStateToProps({ series: {
      shows: {
        items: [],
      },
    } })).toMatchSnapshot();
  });
});
