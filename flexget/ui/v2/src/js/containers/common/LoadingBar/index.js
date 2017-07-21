import { connect } from 'react-redux';
import LoadingBar from 'components/common/LoadingBar';

export function mapStateToProps({ status }, { types } = {}) {
  const namespaces = Object.values(status.loading);
  return {
    loading: !!(types ? types.find(type => namespaces.includes(type)) : namespaces.length !== 0),
  };
}

export default connect(mapStateToProps)(LoadingBar);
