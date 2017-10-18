import React from 'react';
import renderer from 'react-test-renderer';
import { mapStateToProps, LoadingBar } from 'common/LoadingBar';
import { themed } from 'utils/tests';

describe('common/LoadingBar', () => {
  describe('Component', () => {
    it('should render properly when loading', () => {
      expect(
        renderer.create(themed(<LoadingBar loading />))
      ).toMatchSnapshot();
    });

    it('should render properly when not loading', () => {
      expect(
        renderer.create(themed(<LoadingBar loading />))
      ).toMatchSnapshot();
    });
  });

  describe('mapStateToProps', () => {
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
});
