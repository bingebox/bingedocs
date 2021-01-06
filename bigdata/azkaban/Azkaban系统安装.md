------------------------------------------------------------------------------------
            Azkaban系统安装
------------------------------------------------------------------------------------
# 1. azkaban-solo-server安装
    直接拿azkaban-3.70.0.zip，上传到目标服务器，解压得到: ./azkaban-3.70.0/
	cd ./azkaban-3.70.0/azkaban-solo-server/build/distributions/azkaban-solo-server-0.1.0-SNAPSHOT/
	我们这里运行单机版本。
	启动：./bin/start-solo.sh
	关闭：./bin/shutdown-solo.sh
	启动成功后可访问Azkaban web管理系统, 例如：
	http://192.168.3.5:8081/index
