import React from 'react';
import renderer from 'react-test-renderer';
import LogPage from 'components/log';
import { themed, provider } from 'utils/tests';

describe('components/log', () => {
  xit('renders correctly', () => {
    jest.mock('oboe');
    const tree = renderer.create(
      provider(themed(<LogPage height={100} width={100} />), { log: {
        lines: '400',
        query: '',
        connected: true,
        messages: [],
      } })
    ).toJSON();
    expect(tree).toMatchSnapshot();
    jest.unmock('oboe');
  });
});
