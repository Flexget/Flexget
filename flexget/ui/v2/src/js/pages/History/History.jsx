import React, { Component } from 'react';
import { findDOMNode } from 'react-dom';
import PropTypes from 'prop-types';
import HistoryList from 'pages/History/HistoryList';
import FilterNav from 'pages/History/FilterNav';
import { NoPaddingWrapper } from 'common/styles';

export default class HistoryPage extends Component {
  static propTypes = {
    getHistory: PropTypes.func.isRequired,
  };

  state = {
    grouping: 'time',
    sort: 'time',
    order: 'desc',
  };

  getHistory = page => this.props.getHistory({
    page,
    sort_by: this.state.sort,
    order: this.state.order,
    task: this.state.task,
  });

  setScroll = (node) => { this.scroll = node; }
  restartLoader = () => {
    findDOMNode(this.scroll).scrollIntoView(); // eslint-disable-line react/no-find-dom-node
    this.getHistory(1);
    this.scroll.pageLoaded = 1;
  }

  handleChange = key => event => this.setState({ [key]: event.target.value }, this.restartLoader)
  toggleOrder = () => this.setState({
    order: (this.state.order === 'asc' ? 'desc' : 'asc'),
  }, this.restartLoader)

  render() {
    const { grouping } = this.state;

    return (
      <NoPaddingWrapper>
        <FilterNav
          handleChange={this.handleChange}
          toggleOrder={this.toggleOrder}
          {...this.state}
        />
        <HistoryList
          grouping={grouping}
          getHistory={this.getHistory}
          setScroll={this.setScroll}
          ref={(node) => { this.list = node; }}
        />
      </NoPaddingWrapper>
    );
  }
}
