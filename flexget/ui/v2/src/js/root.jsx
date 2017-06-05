import React from 'react';
import store from 'store';
import history from 'history';
import { Provider } from 'react-redux';
import { Route, Switch } from 'react-router-dom';
import { ConnectedRouter } from 'connected-react-router';
import { MuiThemeProvider, withStyles, createStyleSheet } from 'material-ui/styles';
import appTheme from 'theme';
import PrivateRoute from 'containers/common/PrivateRoute';
import Home from 'components/home';
import Layout from 'containers/layout';
import Login from 'containers/login';

const styleSheet = createStyleSheet('Global', theme => ({
  '@global': {
    body: {
      height: '100%',
      width: '100%',
      backgroundColor: theme.palette.background.contentFrame,
      fontFamily: 'Roboto',
    },
    a: {
      textDecoration: 'none',
    },
  },
}));

const Wrapper = withStyles(styleSheet)(({ children }) => <div>{children}</div>);

const Root = () => (
  <Provider store={store}>
    <ConnectedRouter history={history}>
      <MuiThemeProvider theme={appTheme}>
        <Wrapper>
          <Switch>
            <Route path="/login" component={Login} />
            <Layout>
              <PrivateRoute path="/" exact component={Home} />
            </Layout>
          </Switch>
        </Wrapper>
      </MuiThemeProvider>
    </ConnectedRouter>
  </Provider>
);

export default Root;
