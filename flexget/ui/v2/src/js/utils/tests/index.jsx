import React from 'react';
import { MuiThemeProvider } from 'material-ui/styles';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import configureMockStore from 'redux-mock-store';
import theme from 'theme';

const mockStore = configureMockStore();

export function themed(component) {
  return (
    <MuiThemeProvider theme={theme} >
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

export class Headers {
  constructor(obj) {
    this.headers = obj || {};
  }

  get(key) {
    return this.headers[key];
  }
}

export function createNodeMock(element) {
  if (element.type === 'input') {
    return {
      focus() {},
    };
  }
  return null;
}
