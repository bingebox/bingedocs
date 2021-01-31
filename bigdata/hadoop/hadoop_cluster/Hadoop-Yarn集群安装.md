--------------------------------------
# Hadoop-Yarn 集群安装
--------------------------------------

1. 准备安装包

    安装Java环境：需要JDK8以及以上版本。
    从Hadoop官网下载安装包，当前使用的是hadoop-2.10.0。
    下载地址：https://archive.apache.org/dist/hadoop/common/hadoop-2.10.0/, 下载得到：hadoop-2.10.0.tar.gz。

2. 安装

2.1 系统软硬件环境安装

    先规划好硬件服务器，至少3台以上，形成一个集群。
    首先安装好Linux系统，并在每台机器上安装好Java JDK环境。
    本例是安装到/opt/ncdw/jdk1.8.0_144目录，下面配置环境变量时要一致。

    通常，集群中的一台机器被指定为NameNode，另一台机器被指定为ResourceManager。它们是master节点。
    集群中的其余机器同时充当DataNode和NodeManager, 它们是slave节点。
    注意：我们建立的HadoopYarn集群主要是用来执行Spark和Flink Job的，并不是用hdfs来存储海量数据的，
    hdfs只是用来支持Spark和Flink的jar文件分发的，所以为节省机器资源，我们把NameNode和ResourceManager部署在同一个节点，
    而DataNode和NodeManager也在多个slave节点同时部署，当然DataNode可以少启动一点。

    本案例采用四台服务器来搭建集群：
    192.168.3.1
    192.168.3.2
    192.168.3.3
    192.168.3.4

    在每一台机器上都设置hosts: 
    vi /etc/hosts
    添加四条记录：
    192.168.3.1	hadoop1
    192.168.3.2	hadoop2
    192.168.3.2	hadoop-master
    192.168.3.3	hadoop3
    192.168.3.4	hadoop4
    当然，建议直接在CoreDNS一次性配置更方便，每台机器/etc/resolv.conf上配置：
    nameserver <CoreDNS IP>

    本安装例子做如下规划，特别注意master和slave域名和IP配置:
    master节点为: hadoop2, hadoop-master
    slave节点为：hadoop1、hadoop3、hadoop4、也可以把hadoop2同时作为slave节点(请从实际资源情况和集群稳定性情况考虑吧)
    下面配置环境变量和配置文件时，会使用到这些域名。

    然后把Hadoop安装包上传到所有Linux服务器，创建安装目录：
        mkdir /opt/ncdw
    把hadoop-2.10.0.tar.gz放到/opt/ncdw目录下，解压：
        tar zxvf hadoop-2.10.0.tar.gz
    则/opt/ncdw/hadoop-2.10.0是hadoop yarn安装目录，下面配置时会使用到，要保持一致。

2.2 创建子目录

    在所有节点上，创建需要的子目录：
    cd hadoop-2.10.0/
    mkdir -p dfs/data dfs/name
    mkdir -p logs/hdfs logs/yarn
    mkdir -p tmp/hdfs tmp/yarn 
    当然，你也可以把dfs,logs,tmp软链接到数据分区，防止/分区磁盘满。

3. 设置环境变量

    在所有节点上设置环境变量.
    vi ~/.profile, 添加：
        # 假设jdk安装在/opt/ncdw/目录下, 自己安装实际情况配置线上路径
        export JAVA_HOME=/opt/ncdw/jdk1.8.0_144

        export HADOOP_PREFIX=/opt/ncdw/hadoop-2.10.0
        export HADOOP_HOME=$HADOOP_PREFIX
        export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop

        export HADOOP_YARN_HOME=/opt/ncdw/hadoop-2.10.0
        export YARN_CONF_DIR=$HADOOP_YARN_HOME/etc/hadoop

        export PATH=$JAVA_HOME/bin:$PATH:$HADOOP_HOME/bin
        export HADOOP_CLASSPATH=`hadoop classpath`

    使其生效，执行: . ~/.profile

4. 配置

    所有配置文件和环境脚本文件到放到etc/hadoop/目录下, 进入配置目录:
        cd hadoop-2.10.0/etc/hadoop/
    这里配置文件很多，但只要修改4个.xml配置文件和2个.sh脚本文件, 以及slaves：
        core-site.xml
        hdfs-site.xml
        yarn-site.xml
        capacity-scheduler.xml
        slaves
        hadoop-env.sh
        yarn-env.sh
    因为默认的模板文件基本是空的，需要我们根据官网文档和实际安装情况来配置，为了降低部署难度，
    特提供测试环境使用的6个文件，我们在线上部署时，在提供的文件基础上进行修改就比较简单了。
    节点模板配置文件在：install\hadoop_cluster\config
    我们在这6个模板文件基础之上，按实际情况进行修改，具体修改方法如下章节所述。

4.1 hadoop-env.sh

    主要把以下配置项的路径，按实际情况进行配置：
    JAVA_HOME=/opt/ncdw/jdk1.8.0_144
    export HADOOP_PREFIX=/opt/ncdw/hadoop-2.10.0
    export HADOOP_HOME=$HADOOP_PREFIX
    export HADOOP_YARN_HOME=/opt/ncdw/hadoop-2.10.0
    export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
    export HADOOP_LOG_DIR=${HADOOP_HOME}/logs/hdfs
    一般上面没有改动的话，直接用提供的hadoop-env.sh覆盖etc/hadoop下的文件即可。
    注意以上配置必须正确，当我们执行批量启动时，可能出现找不到路径现象，就是配置没有生效。
    不知道为什么env环境变量里的不能读取到，必须在本文件里设置死，郁闷。

4.2 yarn-env.sh

    主要把以下配置项的路径，按实际情况进行配置：
    这里假设运行yarn集群用的是用户honya来执行的，如果是不一样的用户名则改之。
    HADOOP_YARN_USER=honya
    export JAVA_HOME=/opt/ncdw/jdk1.8.0_144
    YARN_CONF_DIR=$HADOOP_YARN_HOME/etc/hadoop
    YARN_LOG_DIR="$HADOOP_YARN_HOME/logs/yarn"

4.3 core-site.xml

    主要修改两项：
    安装路径要填写实际的目录，如: /opt/ncdw/hadoop-2.10.0
    <property>
        <name>hadoop.home</name>
        <value>/opt/ncdw/hadoop-2.10.0</value>
    </property>

    修改hdfs的IP和端口。
    <property>
        <name>fs.defaultFS</name>
        <value>hdfs://hadoop-master:9900</value>
    </property>

4.4 hdfs-site.xml

    主要修改两项：
    安装路径要填写实际的目录，如: /opt/ncdw/hadoop-2.10.0
    <property>
        <name>hadoop.home</name>
        <value>/opt/ncdw/hadoop-2.10.0</value>
    </property>

    修改master节点域名 hadoop-master: (在每台服务器上已经配置/etc/hosts或CoreDNS里配置, 参见1.1节)
    <property>
        <name>dfs.http.address</name>
        <value>hadoop-master:50070</value>
        <description> hdfs namenode web ui 地址 </description>
    </property>

    <property>
        <name>dfs.secondary.http.address</name>
        <value>hadoop-master:50090</value>
        <description> hdfs scondary web ui 地址 </description>
    </property>

4.5 yarn-site.xml

    安装路径要填写实际的目录，如: /opt/ncdw/hadoop-2.10.0
    <property>
        <name>hadoop.home</name>
        <value>/opt/ncdw/hadoop-2.10.0</value>
    </property>

    修改master节点地址: hadoop-master, (在每台服务器上已经配置/etc/hosts或CoreDNS里配置, 参见1.1节)
    <property>
        <name>yarn.resourcemanager.hostname</name>
        <value>hadoop-master</value>
    </property>    

    下面5项的端口号，如果有被其它程序服务所占用，就修改一下，不然不要改动：
    <property>
        <name>yarn.resourcemanager.address</name>
        <value>${yarn.resourcemanager.hostname}:8032</value>
    </property>

    <property>
        <name>yarn.resourcemanager.scheduler.address</name>
        <value>${yarn.resourcemanager.hostname}:8030</value>
    </property>

    <property>
        <name>yarn.resourcemanager.resource-tracker.address</name>
        <value>${yarn.resourcemanager.hostname}:8031</value>
    </property>

    <property>
        <name>yarn.resourcemanager.admin.address</name>
        <value>${yarn.resourcemanager.hostname}:8033</value>
    </property>

    <property>
        <name>yarn.resourcemanager.webapp.address</name>
        <value>${yarn.resourcemanager.hostname}:8088</value>
    </property>

    任务资源调度策略：1) CapacityScheduler: 按队列调度；2) FairScheduler: 平均分配。
    很重要的配置，一定要理解原理, 然后你自己来选择启动哪一种策略。
    <property>
        <description>The class to use as the resource scheduler.</description>
        <name>yarn.resourcemanager.scheduler.class</name>
        <value>org.apache.hadoop.yarn.server.resourcemanager.scheduler.capacity.CapacityScheduler</value>
        <!--
        <value>org.apache.hadoop.yarn.server.resourcemanager.scheduler.fair.FairScheduler</value>
        -->
    </property>

    分配给AM单个容器可申请的最小内存: MB
    <property>
        <description>The minimum allocation for every container request at the RM
        in MBs. Memory requests lower than this will be set to the value of this
        property. Additionally, a node manager that is configured to have less memory
        than this value will be shut down by the resource manager.</description>
        <name>yarn.scheduler.minimum-allocation-mb</name>
        <value>1024</value>
    </property>

    分配给AM单个容器可申请的最大内存: MB
    <property>
        <description>The maximum allocation for every container request at the RM
        in MBs. Memory requests higher than this will throw an
        InvalidResourceRequestException.</description>
        <name>yarn.scheduler.maximum-allocation-mb</name>
        <value>8192</value>
    </property>

    分配给AM单个容器可申请的最小虚拟的CPU个数: 
    <property>
        <description>The minimum allocation for every container request at the RM
        in terms of virtual CPU cores. Requests lower than this will be set to the
        value of this property. Additionally, a node manager that is configured to
        have fewer virtual cores than this value will be shut down by the resource
        manager.</description>
        <name>yarn.scheduler.minimum-allocation-vcores</name>
        <value>1</value>
    </property>

    分配给AM单个容器可申请的最大虚拟的CPU个数: 
    <property>
        <description>The maximum allocation for every container request at the RM
        in terms of virtual CPU cores. Requests higher than this will throw an
        InvalidResourceRequestException.</description>
        <name>yarn.scheduler.maximum-allocation-vcores</name>
        <value>4</value>
    </property>

    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    ****************** 必须根据服务器实际内存来修改 ************************
    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    NodeManager节点最大可用内存, 根据实际机器上的物理内存进行配置：
    NodeManager节点最大Container数量: 
        max(Container) = yarn.nodemanager.resource.memory-mb / yarn.scheduler.maximum-allocation-mb
    <property>
        <description>Amount of physical memory, in MB, that can be allocated
        for containers. If set to -1 and
        yarn.nodemanager.resource.detect-hardware-capabilities is true, it is
        automatically calculated(in case of Windows and Linux).
        In other cases, the default is 8192MB.
        </description>
        <name>yarn.nodemanager.resource.memory-mb</name>
        <value>24576</value>
    </property>

    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    ****************** 必须根据服务器实际CPU来修改 ************************
    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    节点服务器上yarn可以使用的虚拟的CPU个数，默认是8，推荐配置与核心个数相同。
    如果节点CPU的核心个数不足8个，需要调小这个值，yarn不会智能的去检测物理核数。如果机器性能较好，可以配置为物理核数的2倍。
    <property>
        <description>Number of vcores that can be allocated
        for containers. This is used by the RM scheduler when allocating
        resources for containers. This is not used to limit the number of
        CPUs used by YARN containers. If it is set to -1 and
        yarn.nodemanager.resource.detect-hardware-capabilities is true, it is
        automatically determined from the hardware in case of Windows and Linux.
        In other cases, number of vcores is 8 by default.</description>
        <name>yarn.nodemanager.resource.cpu-vcores</name>
        <value>32</value>
    </property>

  下面四项一般不需要修改，除非我们上面创建子目录tmp, logs时不是这样的名称，否则是不需要改动的。
  <property>
    <name>hadoop.tmp.dir</name>
    <value>${hadoop.home}/tmp</value>
  </property>

  <property>
    <name>yarn.log.dir</name>
    <value>${hadoop.home}/logs/yarn</value>
  </property>

  <property>
    <name>yarn.nodemanager.local-dirs</name>
    <value>${hadoop.tmp.dir}/yarn/nm-local-dir</value>
  </property>

  <property>
    <name>yarn.nodemanager.log-dirs</name>
    <value>${yarn.log.dir}/userlogs</value>
  </property>
  
4.6 capacity-scheduler.xml

    <property>
        <name>yarn.scheduler.capacity.resource-calculator</name>
        <!--
        <value>org.apache.hadoop.yarn.util.resource.DefaultResourceCalculator</value>
        -->
        <value>org.apache.hadoop.yarn.util.resource.DominantResourceCalculator</value>
        <description>
            The ResourceCalculator implementation to be used to compare 
            Resources in the scheduler.
            The default i.e. DefaultResourceCalculator only uses Memory while
            DominantResourceCalculator uses dominant-resource to compare 
            multi-dimensional resources such as Memory, CPU etc.
        </description>
    </property>
    注释里的英文已经说明白了，如果采用DefaultResourceCalculator则仅仅计算内存，只有DominantResourceCalculator才同时计算内存和CPU。

4.7 slaves: 从节点域名配置

    hadoop1
    hadoop3
    hadoop4
    hadoop2 (如果在master节点上同时部署slave的话)

4.8 配置文件分发

    一旦这7份配置文件都修改妥当，则把它们分发到所有节点服务器的HADOOP_CONF_DIR目录里，所有节点应当目录规划一致。

5. 运行集群的系统用户账号

    通常，推荐HDFS和YARN集群运行在两个不同的账号下，例如：HDFS采用hdfs用户，YARN采用yarn用户。
    本例中，我们只采用一个账号honya，HDFS和YARN安装目录也在同一台机器上，只是dfs、logs、tmp下建立HDFS和YARN各自子目录而已。
    为了把Hadoop集群运行起来，必须同时启动HDFS和YARN两个集群。

6. 设置ssh免密登录

    为了从master节点免密登录所有slave节点，我们在master节点192.168.3.2上执行：
    ssh-keygen -t rsa -P '' -f ~/.ssh/id_rsa
    在honya用户主目录下.ssh目录里，得到：
    authorized_keys  id_rsa  id_rsa.pub  known_hosts

    先把自己id_rsa.pub添加进authorized_keys:
    cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
    chmod 0600 ~/.ssh/authorized_keys

    现在需要把id_rsa.pub文件分发到所有slave节点，追加到它们.ssh目录里authorized_keys之中。
    scp ~/.ssh/id_rsa.pub honya@192.168.3.1:./
    scp ~/.ssh/id_rsa.pub honya@192.168.3.3:./
    scp ~/.ssh/id_rsa.pub honya@192.168.3.4:./
    
    然后在3台机器上去执行：
    cat ~/id_rsa.pub >> ~/.ssh/authorized_keys
    chmod 0600 ~/.ssh/authorized_keys

    大功告成，我们从192.168.3.2上登录其它4台机器(包括自己，如果自己也作为slave节点的话)试试看：
    ssh honya@192.168.3.1
    ssh honya@192.168.3.2
    ssh honya@192.168.3.3
    ssh honya@192.168.3.4
    应该都是直接进入，不再提示输入密码了。

7. 格式化hdfs
    $HADOOP_PREFIX/bin/hdfs namenode -format <cluster_name>

8. 启动hadoop NameNode daemon和DataNode daemon

8.1 启动/关闭HDFS NameNode:

    在master节点192.168.3.2上执行：hadoop2
    执行:
    $HADOOP_PREFIX/sbin/hadoop-daemon.sh --config $HADOOP_CONF_DIR --script hdfs start namenode
    启动成功后，可以打开管理系统：http://192.168.3.2:50070/

    关闭则执行：
    $HADOOP_PREFIX/sbin/hadoop-daemon.sh --config $HADOOP_CONF_DIR --script hdfs stop namenode

8.2 启动/关闭HDFS DataNode:

    在各个slave节点上执行：这里是3台机器hadoop1, hadoop3, hadoop4
    执行:
    $HADOOP_PREFIX/sbin/hadoop-daemons.sh --config $HADOOP_CONF_DIR --script hdfs start datanode

    关闭则执行：
    $HADOOP_PREFIX/sbin/hadoop-daemons.sh --config $HADOOP_CONF_DIR --script hdfs stop datanode

8.3 启动/关闭所有节点：

    上面我们已经设置了master节点免密登录所有slave节点，则可以在master节点一次性启动整个集群。
    执行:
    $HADOOP_PREFIX/sbin/start-dfs.sh

    关闭则执行：
    $HADOOP_PREFIX/sbin/stop-dfs.sh

9. 启动ResourceManager daemon 和 NodeManager daemon

9.1 启动/关闭ResourceManager节点：

    在master节点192.168.3.2上执行：hadoop2
    执行:
    $HADOOP_YARN_HOME/sbin/yarn-daemon.sh --config $HADOOP_CONF_DIR start resourcemanager
    启动成功后，可以打开管理系统：http://192.168.3.2:8088/

    关闭则执行：
    $HADOOP_YARN_HOME/sbin/yarn-daemon.sh --config $HADOOP_CONF_DIR stop resourcemanager

9.2 启动/关闭NodeManager节点：

    在各个slave节点上执行：这里是3台机器hadoop1, hadoop3, hadoop4
    执行:
    $HADOOP_YARN_HOME/sbin/yarn-daemons.sh --config $HADOOP_CONF_DIR start nodemanager

    关闭则执行：
    $HADOOP_YARN_HOME/sbin/yarn-daemons.sh --config $HADOOP_CONF_DIR stop nodemanager
    
9.3 启动/关闭standalone WebAppProxy server：

    WebAppProxy可以独立部署在一台或多台服务器上，只要你有资源，本例中我们还是和ResourceManager节点同一台机器部署。
    在master节点192.168.3.2上执行：hadoop2
    执行:
    $HADOOP_YARN_HOME/sbin/yarn-daemon.sh --config $HADOOP_CONF_DIR start proxyserver

    关闭则执行：
    $HADOOP_YARN_HOME/sbin/yarn-daemon.sh --config $HADOOP_CONF_DIR stop proxyserver
    
9.4 启动所有节点：

    上面我们已经设置了master节点免密登录所有slave节点，则可以在master节点一次性启动整个集群。
    执行:
    $HADOOP_PREFIX/sbin/start-yarn.sh

    关闭则执行：
    $HADOOP_PREFIX/sbin/stop-yarn.sh
    
10. 整合脚本

    提供[run.sh](./run.sh)脚本，包装集群启动关闭命令，方便运维工作。
honya@hadoop2:~/hadoop-2.10.0$ ./run.sh 
usage: ./run.sh [cmd]
   ./run.sh namenode_format [cluster name]
   ./run.sh start [namenode | datanode]
   ./run.sh stop [namenode | datanode]
   ./run.sh start dfs
   ./run.sh stop dfs
   ./run.sh start [resourcemanager | nodemanager]
   ./run.sh stop [resourcemanager | nodemanager]
   ./run.sh start yarn
   ./run.sh stop yarn
   ./run.sh start proxyserver
   ./run.sh stop proxyserver
   ./run.sh set_env
