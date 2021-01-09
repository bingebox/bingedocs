
kafka_server=192.168.3.4:9092,192.168.3.2:9092,192.168.3.2:9092

if [ "$1" = "desc" ]; then
	./bin/kafka-consumer-groups.sh --bootstrap-server $kafka_server --describe --all-groups
elif [ "$1" = "delete" -a "$#" -ge "2" ]; then
	./bin/kafka-consumer-groups.sh --bootstrap-server $kafka_server --delete --group $2
elif [ "$1" = "offset" -a "$#" -ge "3" ]; then
	./bin/kafka-run-class.sh kafka.tools.GetOffsetShell --broker-list $kafka_server --topic $2 --time $3
else
	echo "usage: run_consumer.sh [cmd] [...]"
	echo "    sh run_consumer.sh desc"
	echo "    sh run_consumer.sh delete [group name]"
	echo "    sh run_consumer.sh offset [topic name] [timestamp flag: -1--latest, -2--earliest]"
fi

