import { connect } from 'react-redux';
import { getVersion } from 'actions/version';
import Version from 'components/layout/Version';

export function mapStateToProps({ version }) {
  return {
    version,
  };
}

function mapDispatchToProps(dispatch) {
  return {
    getVersion: () => dispatch(getVersion()),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(Version);
