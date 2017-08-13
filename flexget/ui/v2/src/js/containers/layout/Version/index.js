import { connect } from 'react-redux';
import { GET_VERSION } from 'actions/version';
import { request } from 'utils/actions';
import Version from 'components/layout/Version';

export function mapStateToProps({ version }) {
  return {
    version,
  };
}

function mapDispatchToProps(dispatch) {
  return {
    getVersion: () => dispatch(request(GET_VERSION)),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(Version);
