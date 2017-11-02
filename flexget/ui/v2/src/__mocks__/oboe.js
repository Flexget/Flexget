export default function oboe() {
  const self = {
    abort: () => self,
    on: () => self,
    fail: () => self,
    done: () => self,
  };

  return self;
}
