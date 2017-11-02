import React from 'react';
import { shallow } from 'enzyme';
import { themed } from '../../../utils/tests';
import { mapStateToProps, LogTable } from '../LogTable';


describe('pages/Log/LogTable', () => {
  describe('LogTable', () => {
    it('renders correctly', () => {
      const wrapper = shallow(
        themed(<LogTable messages={[]} />)
      );
      expect(wrapper).toMatchSnapshot();
    });
  });

  describe('mapStateToProps', () => {
    it('should return the right stuff', () => {
      expect(mapStateToProps({ log: {
        messages: [],
      } })).toMatchSnapshot();
    });
  });
});
