import React from 'react';
import { MuiThemeProvider } from 'material-ui/styles';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import configureMockStore from 'redux-mock-store';

const mockStore = configureMockStore();

export function themed(component) {
  return (
    <MuiThemeProvider>
      { component }
    </MuiThemeProvider>
  );
}

export function router(component) {
  return (
    <MemoryRouter>
      { component }
    </MemoryRouter>
  );
}

export function provider(component, state = {}) {
  return (
    <Provider store={mockStore(state)}>
      { component }
    </Provider>
  );
}
