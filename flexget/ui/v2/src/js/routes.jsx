import React from 'react';
import store from 'store';
import history from 'history';
import Home from 'components/home';
import { Provider } from 'react-redux';
import Layout from 'components/layout';
import { Route, Switch } from 'react-router-dom';
import { ConnectedRouter } from 'connected-react-router';
import { MuiThemeProvider, createMuiTheme } from 'material-ui/styles';
import createPalette from 'material-ui/styles/palette';
import { orange, blueGrey, red } from 'material-ui/styles/colors';

const theme = createMuiTheme({
  palette: createPalette({
    primary: {
      ...orange,
      contrastDefaultColor: 'light',
    },
    accent: blueGrey,
    error: red,
  }),
});

const Root = () => (
  <Provider store={store}>
    <ConnectedRouter history={history}>
      <MuiThemeProvider theme={theme}>
        <Layout>
          <Switch>
            <Route path="/" exact component={Home} />
          </Switch>
        </Layout>
      </MuiThemeProvider>
    </ConnectedRouter>
  </Provider>
);

export default Root;
