import { connect } from 'react-redux';
import { GET_VERSION } from 'store/version/actions';
import { request } from 'utils/actions';
import Version from './Version';

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
export { Version };
