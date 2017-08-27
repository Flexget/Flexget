import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import classNames from 'classnames';
import Icon from 'material-ui/Icon';
import Version from 'containers/layout/Version';
import 'font-awesome/css/font-awesome.css';
import {
  ListWrapper,
  Label,
  colorClass,
  NavList,
  NavItem,
  NavButton,
  NavVersion,
} from './styles';

const sideNavItems = [
  {
    link: '/log',
    icon: 'file-text-o',
    label: 'Log',
  },
  {
    link: '/execute',
    icon: 'cog',
    label: 'Execute',
  },
  {
    link: '/config',
    icon: 'pencil',
    label: 'Config',
  },
  {
    link: '/history',
    icon: 'history',
    label: 'History',
  },
  {
    link: '/movies',
    icon: 'film',
    label: 'Movies',
  },
  {
    link: '/pending',
    icon: 'check',
    label: 'Pending',
  },
  {
    link: '/schedule',
    icon: 'calendar',
    label: 'Schedule',
  },
  {
    link: '/seen',
    icon: 'eye',
    label: 'Seen',
  },
  {
    link: '/series',
    icon: 'tv',
    label: 'Series',
  },
  {
    link: '/status',
    icon: 'heartbeat',
    label: 'Status',
  },
];

class SideNav extends Component {
  static propTypes = {
    sideBarOpen: PropTypes.bool.isRequired,
    toggle: PropTypes.func.isRequired,
  };

  toggleOnMobile = () => {
    if (
      window.matchMedia &&
      window.matchMedia('(max-width: 600px)').matches
    ) {
      this.props.toggle();
    }
  }

  renderNavItems() {
    const { sideBarOpen } = this.props;
    return sideNavItems.map(({ link, icon, label }) => (
      <Link to={link} key={link}>
        <NavItem onClick={this.toggleOnMobile}>
          <NavButton color="accent">
            <Icon className={classNames('fa', `fa-${icon}`, colorClass)} />
            <Label open={sideBarOpen}>
              {label}
            </Label>
          </NavButton>
        </NavItem>
      </Link>
    ));
  }

  render() {
    const { sideBarOpen } = this.props;
    return (
      <ListWrapper elevation={16} open={sideBarOpen}>
        <NavList>
          { ::this.renderNavItems() }
        </NavList>
        <NavVersion hide={!sideBarOpen}>
          <Version />
        </NavVersion>
      </ListWrapper>
    );
  }
}

export default SideNav;
