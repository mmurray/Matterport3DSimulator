#!/bin/bash

# Run both docker containers in the background
docker run -d -v $(pwd)/www/client:/client -v $(pwd)/www/log:/log vln:chat-server
docker run -d -v $(pwd)/www:/var/www/site -p 80:80 vln:chat-www
