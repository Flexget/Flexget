FlexGet CI/CD
=============

FlexGet uses CircleCI for testing, building and deploying FlexGet.

Images
=======
FlexGet tests require specific OS binaries such as unrar. For speed and performance, these binaries are pre-installed on docker images which are managed and maintained by the FlexGet team.

Updating Images
---------------
Updating the docker images may be required from time to time. The following steps outline the process to upgrade the docker images.

The docker images are located in `.circleci/images`

**# Step 1 - Install docker**

Follow the install steps for your specific OS: https://docs.docker.com/engine/installation/

**# Step 2 - Build the images**
Build the updated image::

    docker build -t flexget/cci-python:<version> <folder>


**# Step 3 - Push to dockerhub**
You will require access to https://hub.docker.com/u/flexget/dashboard/

Login and push the image to DockerHub::

   docker login
   docker push flexget/cci-python:<version>


Manual Deploy
-------------
The deploy/release job can be manually triggered if required.

**WARNING: Manually triggering the deploy job WILL NOT ensure tests are passing**::

    curl -u ${CIRCLE_API_TOKEN} -d "build_parameters[CIRCLE_JOB]=deploy" https://circleci.com/api/v1.1/project/github/Flexget/Flexget/tree/develop

