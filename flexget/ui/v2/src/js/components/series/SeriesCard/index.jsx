import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from 'material-ui/styles';
import Card, { CardMedia, CardContent } from 'material-ui/Card';
import Typography from 'material-ui/Typography';
import blank from 'images/blank-banner.png';

const styleSheet = theme => ({
  media: {
    borderBottom: `1px solid ${theme.palette.grey[300]}`,
  },
  image: {
    width: '100%',
    height: 'auto',
    visibility: 'hidden',
  },
});


const SeriesCard = ({ classes, show }) => (
  <Card>
    <CardMedia
      className={classes.media}
      image={show.lookup.tvdb.banner || ''}
      title={show.lookup.tvdb.series_name}
    >
      <img
        src={show.lookup.tvdb.banner || blank}
        className={classes.image}
        alt=""
      />
    </CardMedia>
    <CardContent>
      <Typography type="headline" component="h2">
        {show.name}
      </Typography>
    </CardContent>
  </Card>
);

SeriesCard.propTypes = {
  show: PropTypes.shape({
    name: PropTypes.string,
    lookup: PropTypes.shape({
      tvdb: PropTypes.shape({
        banner: PropTypes.string,
        series_name: PropTypes.string,
      }),
    }),
  }).isRequired,
  classes: PropTypes.object.isRequired,
};

export default withStyles(styleSheet)(SeriesCard);
