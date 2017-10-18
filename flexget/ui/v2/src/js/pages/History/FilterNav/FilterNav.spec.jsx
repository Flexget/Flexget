import React from 'react';
import renderer from 'react-test-renderer';
import FilterNav from 'pages/History/FilterNav';

describe('pages/History/FilterNav', () => {
  it('renders correctly', () => {
    const tree = renderer.create(
      <FilterNav
        handleChange={jest.fn()}
        toggleOrder={jest.fn()}
        grouping="time"
        sort="time"
      />
    ).toJSON();
    expect(tree).toMatchSnapshot();
  });
});
