function status(response) {
  return response.json().then((data) => {
    if (response.status >= 200 && response.status < 300) {
      return { data, headers: response.headers };
    }
    const err = new Error(data.message);
    err.status = response.status;
    throw err;
  });
}

function request(resource, method, body) {
  const contentType = method === 'get' ? {} : { 'Content-Type': 'application/json' };
  return fetch(`/api${resource}`, {
    method,
    headers: {
      Accept: 'application/json',
      ...contentType,
    },
    credentials: 'same-origin',
    body: JSON.stringify(body),
  })
    .then(status);
}

export function get(resource) {
  return request(resource, 'get');
}

export function post(resource, body) {
  return request(resource, 'post', body);
}

export function put(resource, body) {
  return request(resource, 'put', body);
}

export function del(resource) {
  return request(resource, 'delete');
}
