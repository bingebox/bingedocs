# kafka安装文档   

1. 上传安装包  
   cd kafka_2.11-2.0.0  

2. 修改配置文件  
	vi config/server.properties:  
	broker.id=0  
	or broker.id=1  
	or broker.id=2      

	listeners=PLAINTEXT://192.168.2.167:9092  
	or listeners=PLAINTEXT://192.168.2.168:9092  
	or listeners=PLAINTEXT://192.168.2.169:9092    

	log.dirs=/home/honya/kafka_2.11-2.0.0/kafka-logs  
	zookeeper.connect=192.168.2.167:2181,192.168.2.168:2181,192.168.2.169:2181  

3. 启动/关闭  
	bin/kafka-server-start.sh -daemon config/server.properties  
	bin/kafka-server-stop.sh  
	
4. 设置开机自启动  
	sudo vi /etc/rc.local:  

		su - honya -c 'cd /home/honya/kafka_2.11-2.0.0;bin/kafka-server-start.sh -daemon config/server.properties'	

5. 开发注意事项：  
* 5.1 消费者组中的消费者实例个数不能超过分区的数量。  
* 5.2 对于具有N个副本的主题，我们最多容忍N-1个服务器故障，从而保证不会丢失任何提交到日志中的记录.  
