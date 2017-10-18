import { mapStateToProps } from 'pages/Series';

describe('containers/series', () => {
  it('should return the right stuff', () => {
    expect(mapStateToProps({ series: {
      shows: {
        items: [],
      },
    } })).toMatchSnapshot();
  });
});
