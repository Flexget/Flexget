import React from 'react';
import store from 'store';
import history from 'history';
import { Provider } from 'react-redux';
import { Route, Switch } from 'react-router-dom';
import { ConnectedRouter } from 'connected-react-router';
import { MuiThemeProvider } from 'material-ui/styles';
import theme from 'theme';
import PrivateRoute from 'containers/common/PrivateRoute';
import Home from 'components/home';
import Layout from 'containers/layout';
import Login from 'containers/login';

const Root = () => (
  <Provider store={store}>
    <ConnectedRouter history={history}>
      <MuiThemeProvider theme={theme}>
        <Switch>
          <Route path="/login" component={Login} />
          <Layout>
            <PrivateRoute path="/" exact component={Home} />
          </Layout>
        </Switch>
      </MuiThemeProvider>
    </ConnectedRouter>
  </Provider>
);

export default Root;
