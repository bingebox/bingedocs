# kafka安装文档   

1. 上传安装包  
   cd kafka_2.11-2.0.0  

2. 修改配置文件  
	vi config/server.properties:  
        # Kafka broker的id, 从0开始，一个节点一个唯一性编号: 0, 1, 2 
        broker.id=0  

        # socker server的侦听地址 
        listeners=PLAINTEXT://192.168.3.4:9092  

        num.network.threads=3
        num.io.threads=8
        socket.send.buffer.bytes=102400
        socket.receive.buffer.bytes=102400
        socket.request.max.bytes=104857600
        message.max.bytes=10240000
        replica.fetch.max.bytes=20480000

        log.dirs=/home/honya/kafka_2.11-2.0.0/data
        num.partitions=9 

        log.retention.hours=168  

        zookeeper.connect=192.168.3.2:2181,192.168.3.3:2181,192.168.3.4:2181  

3. 启动/关闭  
	bin/kafka-server-start.sh -daemon config/server.properties  
	bin/kafka-server-stop.sh  
	
4. 设置开机自启动  
	sudo vi /etc/rc.local:  

		su - honya -c 'cd /home/honya/kafka_2.11-2.0.0;bin/kafka-server-start.sh -daemon config/server.properties'	

5. 开发注意事项：  
* 5.1 消费者组中的消费者实例个数不能超过分区的数量。  
* 5.2 对于具有N个副本的主题，我们最多容忍N-1个服务器故障，从而保证不会丢失任何提交到日志中的记录.  
