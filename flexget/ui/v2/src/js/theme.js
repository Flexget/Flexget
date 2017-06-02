import { createMuiTheme } from 'material-ui/styles';
import createPalette from 'material-ui/styles/palette';
import { orange, blueGrey, amber } from 'material-ui/styles/colors';

export default createMuiTheme({
  palette: {
    ...createPalette({
      primary: orange,
      accent: blueGrey,
    }),
    secondary: amber,
  },
});
