export const createAction = namespace => (type, payload, message, ignore = false) => ({
  type,
  payload,
  error: (payload instanceof Error),
  meta: {
    ignore,
    message,
    namespace,
  },
});

export const createLoading = namespace => type => ({
  type,
  meta: {
    namespace,
    loading: true,
  },
});
