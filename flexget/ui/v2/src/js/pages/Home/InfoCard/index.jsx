import React from 'react';
import { CardContent } from 'material-ui/Card';
import IconButton from 'material-ui/IconButton';
import Icon from 'material-ui/Icon';
import 'font-awesome/css/font-awesome.css';
import {
  InfoCardWrapper,
  InfoCardHeader,
  BoldParagraph,
  InfoCardActions,
} from './styles';

const InfoCard = () => (
  <InfoCardWrapper>
    <InfoCardHeader
      title="Flexget Web Interface"
      subheader="Under Development"
    />
    <CardContent>
      <BoldParagraph>
        We need your help! If you are a React developer or can help with the layout/design/css
        then please join in the effort!
      </BoldParagraph>
      <p>
        The interface is not yet ready for end users. Consider this preview only state.
      </p>
      <p>
        If you still use it anyways, please report back to us on how well it works, issues,
        ideas etc...
      </p>
      <p>
        There is a functional API with documentation available at <a href="/api">/api</a>
      </p>
      <p>
        More information: <a
          href="http://flexget.com/wiki/Web-UI/v2"
          target="_blank"
          rel="noopener noreferrer"
        >
          http://flexget.com/wiki/Web-UI/v2
        </a>
      </p>
      <p>
        Gitter Chat: <a
          href="https://gitter.im/Flexget/Flexget"
          target="_blank"
          rel="noopener noreferrer"
        >
          https://gitter.im/Flexget/Flexget
        </a>
      </p>
    </CardContent>
    <InfoCardActions>
      <IconButton
        aria-label="Github"
        href="https://github.com/Flexget/Flexget"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Icon className="fa fa-github" />
      </IconButton>
      <IconButton
        aria-label="Flexget.com"
        href="https://flexget.com"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Icon className="fa fa-home" />
      </IconButton>
      <IconButton
        aria-label="Gitter"
        href="https://gitter.im/Flexget/Flexget"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Icon className="fa fa-comment" />
      </IconButton>
      <IconButton
        aria-label="Forum"
        href="https://discuss.flexget.com"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Icon className="fa fa-forumbee" />
      </IconButton>
    </InfoCardActions>
  </InfoCardWrapper>
);

export default InfoCard;
