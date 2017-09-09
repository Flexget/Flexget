import React, { Component } from 'react';
import PropTypes from 'prop-types';
import HistoryList from 'containers/history/HistoryList';

export default class HistoryPage extends Component {
  static propTypes = {
    getHistory: PropTypes.func.isRequired,
  };

  state = {
    grouping: 'time',
    query: {
      sort_by: 'time',
      order: 'desc',
    },
  };

  getHistory = page => this.props.getHistory({ page, ...this.state.query })

  changeGrouping = grouping => this.setState({ grouping })

  changeQuery = query => this.setState({ query })

  restartLoader = () => { this.list.scroller.pageLoaded = 0; }

  render() {
    const { grouping } = this.state;

    return (
      <HistoryList
        grouping={grouping}
        getHistory={this.getHistory}
        ref={(node) => { this.list = node; }}
      />
    );
  }
}
