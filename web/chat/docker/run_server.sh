#!/bin/bash

# Run the python server
docker run -it --rm \
    -v $(pwd)/scripts/Server.py:/Server.py \
    -v $(pwd)/www/client:/client \
    -v $(pwd)/www/log:/log \
    -v $(pwd)/scripts/resources/house_target_tuple.json:/house_target_tuple.json \
    vln:chat-server
