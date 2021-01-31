# zookeeper安装文档    

1. 上传安装包  
    zookeeper-3.4.12

2. 创建相关目录  
    cd ./zookeeper-3.4.12/  
    mkdir data logs  

3. 修改配置文件   
    mv zoo_sample.cfg zoo.cfg  
    vi conf/zoo.cfg:  

        dataDir=/home/honya/zookeeper-3.4.12/data

        server.1=192.168.2.167:2888:3888
        server.2=192.168.2.168:2888:3888
        server.3=192.168.2.169:2888:3888

    vi conf/log4j.properties:  

        zookeeper.root.logger=INFO, ROLLINGFILE
        zookeeper.console.threshold=INFO
        zookeeper.log.dir=/home/honya/zookeeper-3.4.12/logs
        zookeeper.log.file=zookeeper.log
        zookeeper.log.threshold=DEBUG
        zookeeper.tracelog.dir=/home/honya/zookeeper-3.4.12/logs
        zookeeper.tracelog.file=zookeeper_trace.log

4. 启动/关闭  
	bin/zkServer.sh start  
	bin/zkServer.sh status  
	bin/zkServer.sh stop  

5. 设置开机自启动  
	sudo vi /etc/rc.local:  

        su - honya -c 'cd /home/honya/zookeeper-3.4.12;bin/zkServer.sh start'	
