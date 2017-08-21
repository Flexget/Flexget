import { connect } from 'react-redux';
import {
  GET_SHOWS,
} from 'actions/series/shows';
import SeriesPage from 'components/series';
import { request } from 'utils/actions';

function mapStateToProps({ series }) {
  return {
    shows: series.shows.items,
  };
}

function mapDispatchToProps(dispatch) {
  return {
    getShows: payload => dispatch(request(GET_SHOWS, payload)),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(SeriesPage);
