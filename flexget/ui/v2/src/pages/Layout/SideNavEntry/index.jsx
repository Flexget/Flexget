import React from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { ListItemIcon } from 'material-ui/List';
import {
  SideNavIcon,
  SideNavText,
  NavItem,
} from './styles';

const SideNavEntry = ({ onClick, link, icon, label, className }) => {
  const item = (
    <NavItem className={className} onClick={onClick}>
      <ListItemIcon><SideNavIcon className={`fa fa-${icon}`} /></ListItemIcon>
      <SideNavText disableTypography inset primary={label} />
    </NavItem>
  );

  if (link) {
    return <Link to={link}>{item}</Link>;
  }

  return item;
};

SideNavEntry.propTypes = {
  onClick: PropTypes.func.isRequired,
  link: PropTypes.string,
  icon: PropTypes.string.isRequired,
  label: PropTypes.string.isRequired,
  className: PropTypes.string,
};

SideNavEntry.defaultProps = {
  className: '',
  link: '',
};

export default SideNavEntry;
