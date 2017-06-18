import React from 'react';
import PropTypes from 'prop-types';
import Card, { CardActions, CardContent, CardHeader } from 'material-ui/Card';
import { withStyles, createStyleSheet } from 'material-ui/styles';
import IconButton from 'material-ui/IconButton';
import Icon from 'material-ui/Icon';
import 'font-awesome/css/font-awesome.css';

const styleSheet = createStyleSheet('InfoCard', theme => ({
  card: {
    margin: '0 auto',
    [theme.breakpoints.up('sm')]: {
      width: '50%',
    },
  },
  cardHeader: {
    backgroundColor: theme.palette.primary[800],
  },
  boldText: {
    fontWeight: 'bold',
  },
  cardActions: {
    justifyContent: 'center',
  },
}));

const InfoCard = ({ classes }) => (
  <Card className={classes.card}>
    <CardHeader
      className={classes.cardHeader}
      title="Flexget Web Interface"
      subheader="Under Development"
    />
    <CardContent>
      <p className={classes.boldText}>
        We need your help! If you are a React developer or can help with the layout/design/css
        then please join in the effort!
      </p>
      <p>
        The interface is not yet ready for end users. Consider this preview only state.
      </p>
      <p>
        If you still use it anyways, please report back to us on how well it works, issues,
        ideas etc...
      </p>
      <p>
        There is a functional API with documentation available at <a href="/api">/api</a>
      </p>
      <p>
        More information: <a
          href="http://flexget.com/wiki/Web-UI/v2"
          target="_blank"
          rel="noopener noreferrer"
        >
          http://flexget.com/wiki/Web-UI/v2
        </a>
      </p>
      <p>
        Gitter Chat: <a
          href="https://gitter.im/Flexget/Flexget"
          target="_blank"
          rel="noopener noreferrer"
        >
          https://gitter.im/Flexget/Flexget
        </a>
      </p>
    </CardContent>
    <CardActions className={classes.cardActions}>
      <IconButton
        aria-label="Github"
        href="https://github.com/Flexget/Flexget"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Icon className="fa fa-github" />
      </IconButton>
      <IconButton
        aria-label="Flexget.com"
        href="https://flexget.com"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Icon className="fa fa-home" />
      </IconButton>
      <IconButton
        aria-label="Gitter"
        href="https://gitter.im/Flexget/Flexget"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Icon className="fa fa-comment" />
      </IconButton>
      <IconButton
        aria-label="Forum"
        href="https://discuss.flexget.com"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Icon className="fa fa-forumbee" />
      </IconButton>
    </CardActions>
  </Card>
);

InfoCard.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default withStyles(styleSheet)(InfoCard);
