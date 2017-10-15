import React from 'react';
import createStore from 'store';
import history from 'history';
import { JssProvider } from 'react-jss';
import { create } from 'jss';
import preset from 'jss-preset-default';
import createGenerateClassName from 'material-ui/styles/createGenerateClassName';
import { Provider } from 'react-redux';
import { Route, Switch } from 'react-router-dom';
import { ConnectedRouter } from 'connected-react-router';
import { MuiThemeProvider } from 'material-ui/styles';
import { injectGlobal } from 'react-emotion';
import theme from 'theme';
import PrivateRoute from 'common/PrivateRoute';
import Layout from 'pages/Layout';
import { createAsyncComponent } from 'utils/loading';

// eslint-disable-next-line no-unused-expressions
injectGlobal`
  html {
    font-size: 10px;
  }

  body {
    height: 100%;
    width: 100%;
    font-size: 1.6rem;
    background-color: ${theme.palette.background.contentFrame};
    font-family: 'Roboto';
  }

  a {
    text-decoration: none;
  }

  * {
    box-sizing: border-box;
  }

  *:focus {
    outline: none;
  }
`;

const Home = createAsyncComponent(() => import('pages/Home'));
const Log = createAsyncComponent(() => import('pages/Log'));
const Login = createAsyncComponent(() => import('pages/Login'));
const Series = createAsyncComponent(() => import('pages/Series'));
const History = createAsyncComponent(() => import('pages/History'));

const jss = create(preset());
jss.options.createGenerateClassName = createGenerateClassName;
jss.options.insertionPoint = 'material-ui';

const Root = () => (
  <JssProvider jss={jss}>
    <Provider store={createStore()}>
      <ConnectedRouter history={history}>
        <MuiThemeProvider theme={theme}>
          <div>
            <Switch>
              <Route path="/login" exact component={Login} />
              <Layout>
                <Switch>
                  <PrivateRoute path="/" exact component={Home} />
                  <PrivateRoute path="/log" exact component={Log} />
                  <PrivateRoute path="/series" exact component={Series} />
                  <PrivateRoute path="/history" exact component={History} />
                </Switch>
              </Layout>
            </Switch>
          </div>
        </MuiThemeProvider>
      </ConnectedRouter>
    </Provider>
  </JssProvider>
);

export default Root;
