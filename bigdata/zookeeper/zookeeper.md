# zookeeper install  

1. JDK install, JAVA_HOME and PATH setting  
2. cd zookeeper-3.4.12, mkdir data logs  
3. mv zoo_sample.cfg zoo.cfg  
4. vi conf/zoo.cfg:  
	dataDir=/home/honya/zookeeper-3.4.12/data

        server.1=192.168.2.167:2888:3888
        server.2=192.168.2.168:2888:3888
        server.3=192.168.2.169:2888:3888

5. vi conf/log4j.properties:  

        zookeeper.root.logger=INFO, ROLLINGFILE
        zookeeper.console.threshold=INFO
        zookeeper.log.dir=/home/honya/zookeeper-3.4.12/logs
        zookeeper.log.file=zookeeper.log
        zookeeper.log.threshold=DEBUG
        zookeeper.tracelog.dir=/home/honya/zookeeper-3.4.12/logs
        zookeeper.tracelog.file=zookeeper_trace.log

6. cmd:  
	bin/zkServer.sh start  
	bin/zkServer.sh status  
	bin/zkServer.sh stop  

7. su - root, cd /etc, vi rc.local:  

        su - honya -c 'cd /home/honya/zookeeper-3.4.12;bin/zkServer.sh start'	
        
8. /etc/rc.local  
