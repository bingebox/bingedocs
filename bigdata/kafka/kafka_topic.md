# Kafka Topic

1. 删除主题Topic
    在server.properties中增加设置，默认是未开启的，执行：  
    vi ./config/server.properties

        delete.topic.enable=true  
    这样执行删除Topic命令，就是真删除，否则只是做一个标记，磁盘并不得到释放。  
    删除Topic命令：  
    ./bin/kafka-topics.sh --delete --zookeeper [zookeeper_host:2181] --topic [topic name]  

2. 分片partition和副本replication
   执行命令:  
   ./bin/kafka-topics.sh --zookeeper [zookeeper_host:2181] --describe --topic [topic name]  
   例如, 查看主题test1, 得到结果:   
   Topic: test1	PartitionCount: 3	ReplicationFactor: 2	Configs:   
	Topic: test1	Partition: 0	Leader: 1	Replicas: 0,1	Isr: 1,0  
	Topic: test1	Partition: 1	Leader: 1	Replicas: 1,2	Isr: 1,2  
	Topic: test1	Partition: 2	Leader: 2	Replicas: 2,0	Isr: 2,0  
    第一行显示分片信息摘要：Topic test1有3个分片，2个副本。
    第二行显示编号0的分片信息：编号0，Leader在1节点上，Replicas显示两个副本在0节点和1节点， Isr显示存活状态的副本。  
    第三行显示编号1的分片信息，第四行显示编号2的分片信息，类似。
    Leader是在给出的所有Partitons中负责读写的节点，每个节点都有可能成为Leader。  
    Replicas显示给定partiton所有副本所存储节点的节点列表，不管该节点是否是Leader, 或者是否存活。  
    Isr显示副本都已同步的的节点集合，这个集合中的所有节点都是存活状态，并且跟Leader同步。  
