import { LOADING_STATUS } from 'actions/status';

export const action = (type, payload, {
  message,
} = {}) => ({
  type,
  payload,
  error: (payload instanceof Error),
  meta: {
    message,
  },
});

export const request = (type, payload = {}) => ({
  type: LOADING_STATUS,
  payload,
  meta: { type },
});

export const requesting = type => act => (
  act.type === LOADING_STATUS &&
    act.meta.type === type
);
