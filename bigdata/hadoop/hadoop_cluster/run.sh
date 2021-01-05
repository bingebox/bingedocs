#!/bin/bash
#

namenode_format()
{
	cluster_name=$1
	echo "cluster_name=${cluster_name}, format..."
	$HADOOP_PREFIX/bin/hdfs namenode -format $cluster_name
}

start()
{
	type=$1
	if [ "$type" = "namenode" ]; then
		$HADOOP_PREFIX/sbin/hadoop-daemon.sh --config $HADOOP_CONF_DIR --script hdfs start namenode
	elif [ "$type" = "datanode" ]; then
		$HADOOP_PREFIX/sbin/hadoop-daemons.sh --config $HADOOP_CONF_DIR --script hdfs start datanode
	elif [ "$type" = "resourcemanager" ]; then
		$HADOOP_YARN_HOME/sbin/yarn-daemon.sh --config $HADOOP_CONF_DIR start resourcemanager
	elif [ "$type" = "nodemanager" ]; then
		$HADOOP_YARN_HOME/sbin/yarn-daemon.sh --config $HADOOP_CONF_DIR start nodemanager
	elif [ "$type" = "proxyserver" ]; then
		$HADOOP_YARN_HOME/sbin/yarn-daemon.sh --config $HADOOP_CONF_DIR start proxyserver
	elif [ "$type" = "dfs" ]; then
		$HADOOP_PREFIX/sbin/start-dfs.sh
	elif [ "$type" = "yarn" ]; then
		$HADOOP_PREFIX/sbin/start-yarn.sh
	else 
		echo "no supported: $type"
	fi
}

stop()
{
	type=$1
	if [ "$type" = "namenode" ]; then
		$HADOOP_PREFIX/sbin/hadoop-daemon.sh --config $HADOOP_CONF_DIR --script hdfs stop namenode
	elif [ "$type" = "datanode" ]; then
		$HADOOP_PREFIX/sbin/hadoop-daemons.sh --config $HADOOP_CONF_DIR --script hdfs stop datanode
	elif [ "$type" = "resourcemanager" ]; then
		$HADOOP_YARN_HOME/sbin/yarn-daemon.sh --config $HADOOP_CONF_DIR stop resourcemanager
	elif [ "$type" = "nodemanager" ]; then
		$HADOOP_YARN_HOME/sbin/yarn-daemon.sh --config $HADOOP_CONF_DIR stop nodemanager
	elif [ "$type" = "proxyserver" ]; then
		$HADOOP_YARN_HOME/sbin/yarn-daemon.sh --config $HADOOP_CONF_DIR stop proxyserver
	elif [ "$type" = "dfs" ]; then
		$HADOOP_PREFIX/sbin/stop-dfs.sh
	elif [ "$type" = "yarn" ]; then
		$HADOOP_PREFIX/sbin/stop-yarn.sh
	else 
		echo "no supported: $type"
	fi
}

set_env()
{
	export HADOOP_CLASSPATH=`hadoop classpath`
}

usage()
{
	echo "usage: ./run.sh [cmd]"
	echo "   ./run.sh namenode_format [cluster name]"
	echo "----------------------------------------------"
	echo "   ./run.sh start [namenode | datanode]"
	echo "   ./run.sh stop [namenode | datanode]"
	echo "   ./run.sh start dfs"
	echo "   ./run.sh stop dfs"
	echo "----------------------------------------------"
	echo "   ./run.sh start [resourcemanager | nodemanager]"
	echo "   ./run.sh stop [resourcemanager | nodemanager]"
	echo "   ./run.sh start yarn"
	echo "   ./run.sh stop yarn"
	echo "   ./run.sh start proxyserver"
	echo "   ./run.sh stop proxyserver"
	echo "----------------------------------------------"
	echo "   ./run.sh set_env"
}

if [ "$#" -lt "1" ]; then
	usage
elif [ "$1" = "namenode_format" ]; then
	namenode_format $2
elif [ "$1" = "start" ]; then
	start $2
elif [ "$1" = "stop" ]; then 
	stop $2
elif [ "$1" = "env" ]; then 
	set_env
else
	usage
fi
