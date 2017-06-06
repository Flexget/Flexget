import React from 'react';
import renderer from 'react-test-renderer';
import { mount } from 'enzyme';
import Layout from 'components/layout';
import { themed, router, provider } from 'utils/tests';

function renderLayout(checkLogin = jest.fn(), loggedIn = true) {
  return provider(router(themed(
    <Layout loggedIn={loggedIn} checkLogin={checkLogin}>
      <div />
    </Layout>
  )));
}
describe('components/layout', () => {
  it('renders correctly', () => {
    const tree = renderer.create(renderLayout()).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('should check login if not logged In', () => {
    const checkLogin = jest.fn();
    mount(renderLayout(checkLogin, false));
    expect(checkLogin).toHaveBeenCalled();
  });

  it('should not check login if logged In', () => {
    const checkLogin = jest.fn();
    mount(renderLayout(checkLogin));
    expect(checkLogin).not.toHaveBeenCalled();
  });
});

