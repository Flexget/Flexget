import { connect } from 'react-redux';
import LoadingBar from 'components/common/LoadingBar';

export function mapStateToProps({ status }, { prefix = '@flexget' } = {}) {
  return {
    loading: !!(Object.keys(status.loading).find(type => type.startsWith(prefix))),
  };
}

export default connect(mapStateToProps)(LoadingBar);
