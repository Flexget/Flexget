import { mapStateToProps } from 'containers/common/LoadingBar';

describe('containers/common/LoadingBar', () => {
  describe('loading', () => {
    it('should return loading if something is loading without types', () => {
      expect(mapStateToProps({ status: { loading: { '@flexget/a': true } } }).loading).toBe(true);
    });

    it('should return loading if something is loading with types', () => {
      expect(mapStateToProps({ status: { loading: { abracadabra: true } } }, { prefix: 'a' }).loading).toBe(true);
    });
  });

  describe('not loading', () => {
    it('should return not loading if something nothing is loading', () => {
      expect(mapStateToProps({ status: { loading: {} } }).loading).toBe(false);
    });

    it('should return not loading if something is loading with the wrong types', () => {
      expect(mapStateToProps({ status: { loading: { a: true } } }, { prefix: 'b' }).loading).toBe(false);
    });
  });
});
