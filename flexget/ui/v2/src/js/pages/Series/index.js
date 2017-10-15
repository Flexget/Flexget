import { connect } from 'react-redux';
import {
  GET_SHOWS,
} from 'store/series/shows/actions';
import { request } from 'utils/actions';
import Series from './Series';

export function mapStateToProps({ series }) {
  return {
    shows: series.shows.items,
  };
}

function mapDispatchToProps(dispatch) {
  return {
    getShows: payload => dispatch(request(GET_SHOWS, payload)),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(Series);
export { Series };
