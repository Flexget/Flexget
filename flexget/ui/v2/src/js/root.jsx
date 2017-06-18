import React from 'react';
import store from 'store';
import history from 'history';
import { Provider } from 'react-redux';
import { Route, Switch } from 'react-router-dom';
import { ConnectedRouter } from 'connected-react-router';
import { MuiThemeProvider, withStyles, createStyleSheet } from 'material-ui/styles';
import appTheme from 'theme';
import PrivateRoute from 'containers/common/PrivateRoute';
import Layout from 'containers/layout';
import { createAsyncComponent } from 'utils/loading';


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

const Home = createAsyncComponent(() => import('components/home'));
const Log = createAsyncComponent(() => import('components/log'));
const Login = createAsyncComponent(() => import('containers/login'));


const Root = () => (
  <Provider store={store}>
    <ConnectedRouter history={history}>
      <MuiThemeProvider theme={appTheme}>
        <Wrapper>
          <Switch>
            <Route path="/login" exact component={Login} />
            <Layout>
              <Switch>
                <PrivateRoute path="/" exact component={Home} />
                <PrivateRoute path="/log" exact component={Log} />
              </Switch>
            </Layout>
          </Switch>
        </Wrapper>
      </MuiThemeProvider>
    </ConnectedRouter>
  </Provider>
);

export default Root;
