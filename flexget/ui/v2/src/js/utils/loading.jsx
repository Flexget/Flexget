import Loadable from 'react-loadable';
import Loading from 'common/Loader';

export function createAsyncComponent(loader) {
  return Loadable({
    loading: Loading,
    loader,
  });
}
