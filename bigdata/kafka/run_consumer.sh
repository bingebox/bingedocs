#!/bin/bash

server_list=192.168.3.4:9092,192.168.3.3:9092,192.168.3.2:9092

if [ "$1" = "desc_all" ]; then
	./kafka-consumer-groups.sh --bootstrap-server $server_list --describe --all-groups
else 
	echo "usage: ./run_consumer.sh [cmd] [...]"
	echo "     ./run_consumer.sh desc_all"
fi

