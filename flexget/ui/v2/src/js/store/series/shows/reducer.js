import { GET_SHOWS } from 'store/series/shows/actions';

const initState = {
  totalCount: 0,
  items: [],
};

export default function reducer(state = initState, { type, payload }) {
  switch (type) {
    case GET_SHOWS:
      return {
        totalCount: payload.headers.get('total-count'),
        items: payload.data,
      };
    default:
      return state;
  }
}
