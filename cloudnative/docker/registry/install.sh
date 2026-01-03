#!/bin/sh

cd $(dirname "$0")
set -e

gunzip -c images.tar.gz | docker load
docker-compose up -d

sudo cp -f daemon.json /etc/docker/
sudo systemctl restart docker
echo "NOTICE: Please edit /etc/hosts on all nodes (include this one) and point 'myregistry' to IP address of this machine!!!"
echo "NOTICE: Please copy daemon.json to other nodes and run 'sudo systemctl restart docker' to restart docker daemon!!!"
