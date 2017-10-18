import React from 'react';
import renderer from 'react-test-renderer';
import LogPage from 'pages/Log';
import { themed, provider } from 'utils/tests';

describe('pages/Log', () => {
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
