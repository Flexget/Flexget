import { createMuiTheme } from 'material-ui/styles';
import createPalette from 'material-ui/styles/palette';
import orange from 'material-ui/colors/orange';
import blueGrey from 'material-ui/colors/blueGrey';
import amber from 'material-ui/colors/amber';

export default createMuiTheme({
  palette: {
    ...createPalette({
      primary: orange,
      accent: blueGrey,
    }),
    secondary: amber,
  },
});
