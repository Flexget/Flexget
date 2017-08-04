import { LOADING_STATUS } from 'actions/status';

export const createAction = (type, payload, {
  message,
} = {}) => ({
  type,
  payload,
  error: (payload instanceof Error),
  meta: {
    message,
  },
});

export const loading = type => ({
  type: LOADING_STATUS,
  payload: {
    type,
  },
});
