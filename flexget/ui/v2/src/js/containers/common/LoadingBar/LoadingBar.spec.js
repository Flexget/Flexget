import { mapStateToProps } from 'containers/common/LoadingBar';

describe('containers/common/LoadingBar', () => {
  describe('loading', () => {
    it('should return loading if something is loading without types', () => {
      expect(mapStateToProps({ status: { loading: { a: 'b' } } }).loading).toBe(true);
    });

    it('should return loading if something is loading with types', () => {
      expect(mapStateToProps({ status: { loading: { a: 'b' } } }, { types: ['b'] }).loading).toBe(true);
    });
  });

  describe('not loading', () => {
    it('should return not loading if something nothing is loading', () => {
      expect(mapStateToProps({ status: { loading: {} } }).loading).toBe(false);
    });

    it('should return not loading if something is loading with the wrong types', () => {
      expect(mapStateToProps({ status: { loading: { a: 'b' } } }, { types: ['c'] }).loading).toBe(false);
    });
  });
});
