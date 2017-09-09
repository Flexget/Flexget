import React, { Component } from 'react';
import PropTypes from 'prop-types';
import InfiniteScroll from 'react-infinite-scroller';
import List, { ListItem, ListItemText } from 'material-ui/List';
import LoadingSpinner from 'components/common/LoadingSpinner';
import { Subheader, Wrapper } from './styles';

class HistoryList extends Component {
  static propTypes = {
    grouping: PropTypes.oneOf(['time', 'task']).isRequired,
    history: PropTypes.objectOf(PropTypes.arrayOf(PropTypes.shape({
      task: PropTypes.string,
      title: PropTypes.string,
      url: PropTypes.string,
      filename: PropTypes.string,
      details: PropTypes.string,
      time: PropTypes.strings,
      id: PropTypes.number,
    }))).isRequired,
    hasMore: PropTypes.bool,
    getHistory: PropTypes.func.isRequired,
  };

  static defaultProps = {
    hasMore: true,
  };

  render() {
    const { grouping, history, hasMore, getHistory } = this.props;

    return (
      <Wrapper>
        <InfiniteScroll
          hasMore={hasMore}
          loadMore={getHistory}
          loader={<LoadingSpinner loading />}
          ref={(node) => { this.scroller = node; }}
          useWindow={false}
        >
          { Object.entries(history).map(([subheader, histories]) => (
            <List key={subheader} subheader={<Subheader color="primary">{subheader}</Subheader>}>
              {histories.map(({ id, title, time, task }) => (
                <ListItem key={id}>
                  <ListItemText primary={title} secondary={grouping === 'time' ? task : time} />
                </ListItem>
              ))}
            </List>
          ))}
        </InfiniteScroll>
      </Wrapper>
    );
  }
}

export default HistoryList;
