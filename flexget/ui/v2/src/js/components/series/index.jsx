import React, { Component } from 'react';
import PropTypes from 'prop-types';
import SeriesCard from 'components/series/SeriesCard';
import Grid from 'material-ui/Grid';
import { withStyles } from 'material-ui/styles';

const styleSheet = () => ({
  card: {
    width: '100vw',
  },
});

class SeriesPage extends Component {
  static propTypes = {
    shows: PropTypes.arrayOf(PropTypes.object).isRequired,
    getShows: PropTypes.func.isRequired,
    classes: PropTypes.object.isRequired,
  };

  componentDidMount() {
    this.props.getShows();
  }

  render() {
    const { shows, classes } = this.props;

    return (
      <Grid container spacing={24}>
        {shows.map(show => (
          <Grid item key={show.id} sm={12} md={6} className={classes.card}>
            <SeriesCard show={show} />
          </Grid>
        ))}
      </Grid>
    );
  }
}

export default withStyles(styleSheet)(SeriesPage);

