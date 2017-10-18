import React, { Component } from 'react';
import PropTypes from 'prop-types';
import IconButton from 'material-ui/IconButton';
import Select from 'material-ui/Select';
import Input, { InputLabel } from 'material-ui/Input';
import { MenuItem } from 'material-ui/Menu';
import SecondaryNav from 'common/SecondaryNav';
import { Spacer } from 'common/styles';
import { RotatingIcon, PaddedFormControl } from './styles';

const ENTER_KEY = 13;
const groupByFields = [
  {
    value: 'task',
    label: 'Task',
  },
  {
    value: 'time',
    label: 'Time',
  },
];

const sortByFields = [
  {
    value: 'details',
    label: 'Details',
  },
  {
    value: 'filename',
    label: 'Filename',
  },
  {
    value: 'id',
    label: 'ID',
  },
  {
    value: 'task',
    label: 'Task',
  },
  {
    value: 'time',
    label: 'Time',
  },
  {
    value: 'title',
    label: 'Title',
  },
  {
    value: 'url',
    label: 'URL',
  },
];

class FilterNav extends Component {
  static propTypes = {
    order: PropTypes.oneOf(['asc', 'desc']).isRequired,
    grouping: PropTypes.oneOf(groupByFields.map(({ value }) => value)).isRequired,
    sort: PropTypes.oneOf(sortByFields.map(({ value }) => value)).isRequired,
    toggleOrder: PropTypes.func.isRequired,
    handleChange: PropTypes.func.isRequired,
  };

  state = {
    task: '',
  }

  handleChange = (event) => {
    this.setState({ task: event.target.value });
  }

  handleKeyPress = (event) => {
    if (event.which === ENTER_KEY) {
      this.props.handleChange('task')(event);
    }
  }

  render() {
    const {
      order,
      grouping,
      sort,
      toggleOrder,
      handleChange,
    } = this.props;

    const {
      task,
    } = this.state;

    return (
      <SecondaryNav>
        <PaddedFormControl>
          <InputLabel htmlFor="task-filter">
            Filter By Task
          </InputLabel>
          <Input
            id="task-filter"
            placeholder="Task Name"
            value={task}
            onChange={this.handleChange}
            onKeyPress={this.handleKeyPress}
          />
        </PaddedFormControl>
        <Spacer />
        <PaddedFormControl>
          <InputLabel htmlFor="sort-by">Sort By</InputLabel>
          <Select
            value={sort}
            onChange={handleChange('sort')}
            input={<Input id="sort-by" />}
          >
            {sortByFields.map(({ value, label }) => (
              <MenuItem value={value} key={value}>{label}</MenuItem>
            ))}
          </Select>
        </PaddedFormControl>
        <PaddedFormControl>
          <InputLabel htmlFor="group-by">Group By</InputLabel>
          <Select
            value={grouping}
            onChange={handleChange('grouping')}
            input={<Input id="group-by" />}
          >
            {groupByFields.map(({ value, label }) => (
              <MenuItem value={value} key={value}>{label}</MenuItem>
            ))}
          </Select>
        </PaddedFormControl>
        <IconButton color="inherit" onClick={toggleOrder}>
          <RotatingIcon rotate={order === 'desc'} className="fa fa-chevron-up" />
        </IconButton>
      </SecondaryNav>
    );
  }
}

export default FilterNav;
