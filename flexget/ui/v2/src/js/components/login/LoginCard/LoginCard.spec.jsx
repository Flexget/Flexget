import React from 'react';
import renderer from 'react-test-renderer';
import { shallow } from 'enzyme';
import LoginCardFull, { LoginCard } from 'components/login/LoginCard';
import { themed, provider } from 'utils/tests';

describe('components/login/LoginCard', () => {
  it('renders correctly', () => {
    const tree = renderer.create(
      provider(themed(<LoginCardFull />)),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('should call handleSubmit on submit', () => {
    const handleSubmit = jest.fn();
    const wrapper = shallow(<LoginCard
      handleSubmit={handleSubmit}
      classes={{}}
    />);

    wrapper.find('form').simulate('submit');
    expect(handleSubmit).toHaveBeenCalled();
  });
});
