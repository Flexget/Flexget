import { GET_SERIES } from 'actions/series/shows';

const initState = {
  totalCount: 0,
  items: [],
};

export default function reducer(state = initState, { type, payload }) {
  switch (type) {
    case GET_SERIES:
      return {
        totalCount: payload.headers.get('total-count'),
        items: [...state.items, payload.data.items],
      };
    default:
      return state;
  }
}
