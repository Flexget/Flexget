import React from 'react';
import Login from 'components/login';
import renderer from 'react-test-renderer';
import { provider, router, themed } from 'utils/tests';

const Component = () => <div />;
describe('components/login', () => {
  it('renders correctly when logged in', () => {
    const tree = renderer.create(
      router(themed(<Login
        component={Component}
        redirectToReferrer
        location={{}}
      />))
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });

  it('renders correctly when logged out', () => {
    const tree = renderer.create(
      provider(router(themed(<Login
        component={Component}
        redirectToReferrer={false}
        location={{}}
      />)), { status: {} })
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
