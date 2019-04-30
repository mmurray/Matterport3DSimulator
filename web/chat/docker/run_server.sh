#!/bin/bash

# Run the python server
docker run -it --rm \
    -v $(pwd)/scripts/Server.py:/Server.py -v $(pwd)/www/client:/client \
    -v $(pwd)/www/log:/log vln:chat-server
