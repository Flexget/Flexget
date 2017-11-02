export function groupBy(array, key, transform = f => f) {
  return array.reduce((obj, curr) => {
    const modKey = transform(curr[key]);
    return {
      ...obj,
      [modKey]: obj[modKey] ? [...obj[modKey], curr] : [curr],
    };
  }, {});
}
