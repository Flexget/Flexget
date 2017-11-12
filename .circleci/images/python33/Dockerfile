FROM circleci/python:3.3

# Install extra repos
RUN sudo sed -i 's/debian jessie main$/debian jessie main contrib non-free/' /etc/apt/sources.list

# Install unrar used by some flexget tests
RUN sudo apt-get update; sudo apt-get install -qy unrar

# Required as py3.3 venv does not install pip by default
RUN sudo pip install virtualenv
