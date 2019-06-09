#!/bin/bash

# Run both docker containers in the background
docker run -d -v $(pwd)/www/client:/client -v $(pwd)/www/log:/log vln:chat-server
docker run -d \
    -v $(pwd)/www/client:/var/www/site/client -v $(pwd)/www/log:/var/www/site/log -v $(pwd)/www/feedback:/var/www/site/feedback \
    -e "R2R_DATA_PREFIX=https://s3.us-west-2.amazonaws.com/vln/data/v1/r2r" \
    -e "CONNECTIVITY_DATA_PREFIX=https://s3.us-west-2.amazonaws.com/vln/data/v1/connectivity" \
    -e "MATTERPORT_DATA_PREFIX=https://s3.us-west-2.amazonaws.com/vln/data" \
    -p 80:80 vln:chat-www

