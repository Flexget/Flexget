import React from 'react';
import renderer from 'react-test-renderer';
import Header from 'components/log/Header';
import { themed } from 'utils/tests';

describe('components/log/Header', () => {
  it('renders correctly', () => {
    const tree = renderer.create(
      themed(<Header
        start={jest.fn()}
        connected
        setQuery={jest.fn()}
        query=""
        clearLogs={jest.fn()}
        lines="400"
        setLines={jest.fn()}
      />)
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
