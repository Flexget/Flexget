import React from 'react';
import renderer from 'react-test-renderer';
import Version from 'components/layout/Version';
import { themed } from 'utils/tests';

describe('components/layout/Version', () => {
  it('renders correctly with latest version', () => {
    const getVersion = jest.fn();
    const tree = renderer.create(
      themed(<Version version={{ api: '1.1.2', flexget: '2.10.60', latest: '2.10.60' }} getVersion={getVersion} />),
    ).toJSON();
    expect(tree).toMatchSnapshot();
    expect(getVersion).toHaveBeenCalled();
  });

  it('renders correctly without latest version', () => {
    const getVersion = jest.fn();
    const tree = renderer.create(
      themed(<Version version={{ api: '1.1.2', flexget: '2.10.11', latest: '2.10.60' }} getVersion={getVersion} />),
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
