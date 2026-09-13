# OpenSearch 系统安装指南（基于 tar 压缩包方式）

> 本文档翻译并整理自官方文档：<https://docs.opensearch.org/latest/install-and-configure/install-opensearch/tar/>

从 tar 压缩包（又称 tar 归档文件）安装 OpenSearch，适合希望精细控制安装细节（如文件权限、安装路径）的用户。

**安装流程概览：**

1. **下载并解压 OpenSearch**
2. **配置重要的系统设置**（在修改任何 OpenSearch 文件之前，先在宿主机上应用这些设置）
3. **（可选）测试 OpenSearch**
   - 在应用自定义配置之前，先确认 OpenSearch 能够正常运行
   - 可以完全不带安全配置（无密码、无证书）测试，也可以使用压缩包自带的脚本应用演示安全配置
4. **在你的环境中配置 OpenSearch**
   - 应用基础设置，开始在你的环境中使用

tar 压缩包是一个自包含的目录，包含了运行 OpenSearch 所需的一切，包括集成的 Java 开发工具包（JDK）。此安装方式兼容大多数 Linux 发行版，包括 CentOS 7、Amazon Linux 2 和 Ubuntu 18.04。如果你有自己的 Java 安装并在终端中设置了 `JAVA_HOME` 环境变量，macOS 也可以使用。

> **说明**：本指南假设你熟悉 Linux 命令行界面（CLI）操作，能够输入命令、在目录间导航、编辑文本文件。部分示例命令使用了 `vi` 编辑器，你也可以使用任何可用的文本编辑器。

---

## 第一步：下载并解压 OpenSearch

1. 从 [OpenSearch 下载页面](https://opensearch.org/downloads.html) 下载合适的 tar.gz 压缩包，或者使用命令行工具（如 `wget`）下载：

   ```bash
   # x64 架构
   wget https://artifacts.opensearch.org/releases/bundle/opensearch/<版本号>/opensearch-<版本号>-linux-x64.tar.gz

   # ARM64 架构
   wget https://artifacts.opensearch.org/releases/bundle/opensearch/<版本号>/opensearch-<版本号>-linux-arm64.tar.gz
   ```

2. 解压压缩包：

   ```bash
   # x64
   tar -xvf opensearch-<版本号>-linux-x64.tar.gz

   # ARM64
   tar -xvf opensearch-<版本号>-linux-arm64.tar.gz
   ```

---

## 第二步：配置重要的系统设置

启动 OpenSearch 之前，应先查看一些[重要的系统设置](https://docs.opensearch.org/latest/opensearch/install/important-settings/)。

1. 禁用宿主机的内存分页和交换（swap），以提升性能：

   ```bash
   sudo swapoff -a
   ```

2. 增加 OpenSearch 可用的内存映射数量：

   ```bash
   # 编辑 sysctl 配置文件
   sudo vi /etc/sysctl.conf

   # 添加一行来定义期望的值；
   # 如果该键已存在，则修改其值，然后保存更改
   vm.max_map_count=262144

   # 使用 sysctl 重新加载内核参数
   sudo sysctl -p

   # 检查该值，验证更改是否已生效
   cat /proc/sys/vm/max_map_count
   ```

---

## 第三步：（可选）测试 OpenSearch

在继续之前，建议先测试 OpenSearch 的安装。否则，以后出现问题时，可能很难判断问题是由安装本身导致的，还是由你安装后应用的自定义设置导致的。此阶段有两种快速测试方法：

1. **（启用安全）** 使用 tar 压缩包中自带的演示安全脚本应用一套通用配置。
2. **（禁用安全）** 手动禁用 Security 插件，在应用你自己的安全设置之前测试实例。

演示安全脚本会为 OpenSearch 实例应用一套通用配置：它定义了一些环境变量，并应用自签名的 TLS 证书。如果你想自行配置这些内容，请参见【第四步】。

如果你只是想验证服务配置正确，并打算自己配置安全设置，可以禁用 Security 插件，在不启用加密或认证的情况下启动服务。

> ⚠️ **警告**：经演示安全脚本配置的 OpenSearch 节点**不适合生产环境**。如果你计划运行 `opensearch-tar-install.sh` 后将节点用于生产环境，至少应：用你自己的 TLS 证书替换演示 TLS 证书，并更新内部用户和密码列表。有关如何确保节点按安全要求进行配置的更多指导，请参见【安全配置】文档。

### 选项 1：启用安全来测试 OpenSearch

1. 切换到 OpenSearch 安装的顶层目录：

   ```bash
   cd /path/to/opensearch-<版本号>
   ```

2. 以安全演示配置运行 OpenSearch 启动脚本：

   ```bash
   ./opensearch-tar-install.sh
   ```

   对于 OpenSearch 2.12 及更高版本，在安装前使用以下命令设置新的自定义管理员密码（需符合[密码要求](https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/#password-requirements)）：

   ```bash
   export OPENSEARCH_INITIAL_ADMIN_PASSWORD=<自定义管理员密码>
   ```

3. 打开另一个终端会话，向服务器发送请求以验证 OpenSearch 正在运行。注意 `--insecure` 标志——由于 TLS 证书是自签名的，必须使用该标志：

   - 向 9200 端口发送请求：

     ```bash
     curl -X GET https://localhost:9200 -u 'admin:<自定义管理员密码>' --insecure
     ```

     应得到类似如下的响应：

     ```json
     {
        "name" : "hostname",
        "cluster_name" : "opensearch",
        "cluster_uuid" : "6XNc9m2gTUSIoKDqJit0PA",
        "version" : {
           "distribution" : "opensearch",
           "number" : "<版本号>",
           "build_type" : "<构建类型>",
           "build_hash" : "<构建哈希>",
           "build_date" : "<构建日期>",
           "build_snapshot" : false,
           "lucene_version" : "<lucene版本>",
           "minimum_wire_compatibility_version" : "7.10.0",
           "minimum_index_compatibility_version" : "7.0.0"
        },
        "tagline" : "The OpenSearch Project: https://opensearch.org/"
     }
     ```

   - 查询插件端点：

     ```bash
     curl -X GET https://localhost:9200/_cat/plugins?v -u 'admin:<自定义管理员密码>' --insecure
     ```

     响应应类似如下（列出内置插件及其版本）：

     ```
     name     component                            version
     hostname opensearch-alerting                  <版本号>
     hostname opensearch-anomaly-detection         <版本号>
     hostname opensearch-asynchronous-search       <版本号>
     hostname opensearch-cross-cluster-replication <版本号>
     hostname opensearch-index-management          <版本号>
     hostname opensearch-job-scheduler             <版本号>
     hostname opensearch-knn                       <版本号>
     hostname opensearch-ml                        <版本号>
     hostname opensearch-notifications             <版本号>
     hostname opensearch-notifications-core        <版本号>
     hostname opensearch-observability             <版本号>
     hostname opensearch-performance-analyzer      <版本号>
     hostname opensearch-reports-scheduler         <版本号>
     hostname opensearch-security                  <版本号>
     hostname opensearch-sql                       <版本号>
     ```

4. 返回原来的终端会话，按 `CTRL + C` 停止进程。

### 选项 2：禁用安全来测试 OpenSearch

1. 打开配置文件：

   ```bash
   vi /path/to/opensearch-<版本号>/config/opensearch.yml
   ```

2. 添加以下行以禁用 Security 插件：

   ```yaml
   plugins.security.disabled: true
   ```

3. 保存更改并关闭文件。

4. 打开另一个终端会话，向服务器发送请求以验证 OpenSearch 正在运行。由于 Security 插件已禁用，此时使用 `HTTP`（而非 `HTTPS`）发送命令：

   - 向 9200 端口发送请求：

     ```bash
     curl -X GET http://localhost:9200
     ```

   - 查询插件端点：

     ```bash
     curl -X GET http://localhost:9200/_cat/plugins?v
     ```

---

## 第四步：在你的环境中配置 OpenSearch

对 OpenSearch 没有经验的用户，可能需要一份推荐设置清单来启动服务。默认情况下，OpenSearch 不绑定到网络接口，外部主机无法访问；此外，安全设置要么未定义（全新安装），要么（如果运行了演示安全脚本）填满了默认用户名和密码。以下推荐设置可让你：

- 将 OpenSearch 绑定到主机的 IP 或网络接口
- 设置 JVM 堆的初始大小和最大大小
- 定义指向内置 JDK 的环境变量
- 配置你自己的 TLS 证书（无需第三方证书颁发机构 CA）
- 创建具有自定义密码的 admin 用户

> **说明**：如果你运行过演示安全脚本，需要手动重新配置那些被修改过的设置。继续之前请参见【安全配置】文档。

> 💡 **提示**：修改任何配置文件之前，最好先备份一份。备份文件可用于回滚因配置错误引起的问题。

1. 打开 `opensearch.yml`：

   ```bash
   vi /path/to/opensearch-<版本号>/config/opensearch.yml
   ```

2. 添加以下内容：

   ```yaml
   # 将 OpenSearch 绑定到正确的网络接口。
   # 使用 0.0.0.0 表示包含所有可用接口，
   # 或指定分配给特定接口的 IP 地址。
   network.host: 0.0.0.0

   # 除非你已经配置了集群，否则应将 discovery.type
   # 设置为 single-node，否则尝试启动服务时引导检查会失败。
   discovery.type: single-node

   # 如果你之前在 opensearch.yml 中禁用了 Security 插件，
   # 请务必重新启用它。否则可跳过此设置。
   plugins.security.disabled: false
   ```

3. 保存更改并关闭文件。

4. 指定 JVM 堆的初始和最大大小：

   1. 打开 `jvm.options`：

      ```bash
      vi /path/to/opensearch-<版本号>/config/jvm.options
      ```

   2. 修改初始堆大小和最大堆大小的值。作为起点，建议设置为可用系统内存的一半。对于专用主机，可以根据工作负载需求增大该值。
      - 例如，如果主机有 8 GB 内存，可以将初始和最大堆大小设为 4 GB：

        ```
        -Xms4g
        -Xmx4g
        ```

   3. 保存更改并关闭文件。

5. 指定内置 JDK 的位置：

   ```bash
   export OPENSEARCH_JAVA_HOME=/path/to/opensearch-<版本号>/jdk
   ```

### 配置 TLS

TLS 证书为你的集群提供额外的安全保障：允许客户端确认主机身份，并加密客户端与主机之间的流量。开发环境中，自签名证书通常就足够了。以下将指导你完成生成自己的 TLS 证书并应用到 OpenSearch 主机的基本步骤。

1. 进入 OpenSearch 的 `config` 目录（证书将存储在这里）：

   ```bash
   cd /path/to/opensearch-<版本号>/config/
   ```

2. 生成根证书（用于签名其他证书）：

   ```bash
   # 为根证书创建私钥
   openssl genrsa -out root-ca-key.pem 2048

   # 使用私钥创建自签名根证书。
   # 注意：务必替换传给 -subj 的参数，使其反映你具体的主机信息。
   openssl req -new -x509 -sha256 -key root-ca-key.pem \
     -subj "/C=CA/ST=ONTARIO/L=TORONTO/O=ORG/OU=UNIT/CN=ROOT" \
     -out root-ca.pem -days 730
   ```

3. 创建 admin 证书（用于执行 Security 插件管理任务时获得提升权限）：

   ```bash
   # 为 admin 证书创建私钥
   openssl genrsa -out admin-key-temp.pem 2048

   # 将私钥转换为 PKCS#8 格式
   openssl pkcs8 -inform PEM -outform PEM -in admin-key-temp.pem \
     -topk8 -nocrypt -v1 PBE-SHA1-3DES -out admin-key.pem

   # 创建 CSR。CN 为 "A" 是可以接受的，因为此证书
   # 用于提升权限认证，不绑定到具体主机。
   openssl req -new -key admin-key.pem \
     -subj "/C=CA/ST=ONTARIO/L=TORONTO/O=ORG/OU=UNIT/CN=A" \
     -out admin.csr

   # 用前面创建的根证书和私钥签名 admin 证书
   openssl x509 -req -in admin.csr -CA root-ca.pem -CAkey root-ca-key.pem \
     -CAcreateserial -sha256 -out admin.pem -days 730
   ```

4. 为当前要配置的节点创建证书：

   ```bash
   # 为节点证书创建私钥
   openssl genrsa -out node1-key-temp.pem 2048

   # 将私钥转换为 PKCS#8 格式
   openssl pkcs8 -inform PEM -outform PEM -in node1-key-temp.pem \
     -topk8 -nocrypt -v1 PBE-SHA1-3DES -out node1-key.pem

   # 创建 CSR，并替换 -subj 参数以反映你具体的主机。
   # CN 必须匹配该主机的 DNS A 记录——不要使用主机名。
   openssl req -new -key node1-key.pem \
     -subj "/C=CA/ST=ONTARIO/L=TORONTO/O=ORG/OU=UNIT/CN=node1.dns.a-record" \
     -out node1.csr

   # 创建扩展文件，为主机定义 SAN DNS 名称。
   # 应与主机的 DNS A 记录匹配。
   echo 'subjectAltName=DNS:node1.dns.a-record' > node1.ext

   # 用前面创建的根证书和私钥签名节点证书
   openssl x509 -req -in node1.csr -CA root-ca.pem -CAkey root-ca-key.pem \
     -CAcreateserial -sha256 -out node1.pem -days 730 -extfile node1.ext
   ```

5. 删除不再需要的临时文件：

   ```bash
   rm *temp.pem *csr *ext
   ```

6. 按照【生成证书】文档所述，将这些证书添加到 `opensearch.yml`。高级用户也可以选用以下脚本追加设置：

   ```bash
   #! /bin/bash

   # 运行此脚本前，确保将 /path/to 替换为你的 OpenSearch 目录，
   # 并记得将节点 DN 中的 CN 替换为真实的 DNS A 记录。

   echo "plugins.security.ssl.transport.pemcert_filepath: /path/to/opensearch-<版本号>/config/node1.pem" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.ssl.transport.pemkey_filepath: /path/to/opensearch-<版本号>/config/node1-key.pem" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.ssl.transport.pemtrustedcas_filepath: /path/to/opensearch-<版本号>/config/root-ca.pem" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.ssl.http.enabled: true" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.ssl.http.pemcert_filepath: /path/to/opensearch-<版本号>/config/node1.pem" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.ssl.http.pemkey_filepath: /path/to/opensearch-<版本号>/config/node1-key.pem" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.ssl.http.pemtrustedcas_filepath: /path/to/opensearch-<版本号>/config/root-ca.pem" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.allow_default_init_securityindex: true" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.authcz.admin_dn:" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "  - 'CN=A,OU=UNIT,O=ORG,L=TORONTO,ST=ONTARIO,C=CA'" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.nodes_dn:" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "  - 'CN=node1.dns.a-record,OU=UNIT,O=ORG,L=TORONTO,ST=ONTARIO,C=CA'" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.audit.type: internal_opensearch" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.enable_snapshot_restore_privilege: true" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.check_snapshot_restore_write_privileges: true" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   echo "plugins.security.restapi.roles_enabled: [\"all_access\", \"security_rest_api_access\"]" | sudo tee -a /path/to/opensearch-<版本号>/config/opensearch.yml
   ```

7. （可选）为自签名根证书添加信任：

   ```bash
   # 将根证书复制到正确的目录
   sudo cp /path/to/opensearch-<版本号>/config/root-ca.pem /etc/pki/ca-trust/source/anchors/

   # 添加信任
   sudo update-ca-trust
   ```

### 配置用户

OpenSearch 通过多种方式定义和认证用户。其中一种无需额外后端基础设施的方法是：在 `internal_users.yml` 中手动配置用户。以下步骤说明如何删除除 `admin` 用户之外的所有演示用户，并使用脚本替换 `admin` 的默认密码。

1. 使 Security 插件的脚本具有可执行权限：

   ```bash
   chmod 755 /path/to/opensearch-<版本号>/plugins/opensearch-security/tools/*.sh
   ```

2. 运行 `hash.sh` 生成新的密码：

   - 如果未定义 JDK 路径，此脚本会执行失败。

   - 为避免问题，调用脚本时声明环境变量：

     ```bash
     OPENSEARCH_JAVA_HOME=/path/to/opensearch-<版本号>/jdk ./hash.sh
     ```

   - 在提示处输入想要的密码，并记下输出的哈希值。

3. 打开 `internal_users.yml`：

   ```bash
   vi /path/to/opensearch-<版本号>/config/opensearch-security/internal_users.yml
   ```

4. 删除除 `admin` 之外的所有演示用户，并用上一步 `hash.sh` 输出的哈希替换。文件应类似如下：

   ```yaml
   ---
   # 这是内部用户数据库
   # 哈希值使用 bcrypt 生成，可以用 plugin/tools/hash.sh 生成

   _meta:
      type: "internalusers"
      config_version: 2

   # 在此定义你的内部用户

   admin:
      hash: "$2y$1EXAMPLEQqwS8TUcoEXAMPLEeZ3lEHvkEXAMPLERqjyh1icEXAMPLE."
      reserved: true
      backend_roles:
      - "admin"
      description: "Admin user"
   ```

### 应用更改

现在 TLS 证书已安装，演示用户已删除或已设置新密码，最后一步是应用这些配置更改。最后这一步需要在 OpenSearch 于主机上**运行中**的状态下调用 `securityadmin.sh`。

1. 启动 OpenSearch（`securityadmin.sh` 要求 OpenSearch 正在运行才能应用更改）：

   ```bash
   # 切换目录
   cd /path/to/opensearch-<版本号>/bin

   # 以前台方式运行服务
   ./opensearch
   ```

2. 在主机上打开另一个终端会话，进入包含 `securityadmin.sh` 的目录：

   ```bash
   # 切换到正确的目录
   cd /path/to/opensearch-<版本号>/plugins/opensearch-security/tools
   ```

3. 调用脚本（必须传入的参数说明参见官方文档【使用 securityadmin.sh 应用更改】）：

   ```bash
   # 如果已在 $PATH 中声明了该环境变量，可以省略它
   OPENSEARCH_JAVA_HOME=/path/to/opensearch-<版本号>/jdk \
     ./securityadmin.sh \
     -cd /path/to/opensearch-<版本号>/config/opensearch-security/ \
     -cacert /path/to/opensearch-<版本号>/config/root-ca.pem \
     -cert /path/to/opensearch-<版本号>/config/admin.pem \
     -key /path/to/opensearch-<版本号>/config/admin-key.pem \
     -icl -nhnv
   ```

4. 停止并重启正在运行的 OpenSearch 进程以应用更改。

### 验证服务正在运行

此时，OpenSearch 已在你的主机上运行，使用自定义 TLS 证书，并有一个用于基本认证的加密用户。你可以从另一台主机向 OpenSearch 节点发送 API 请求来验证外部连通性。

之前测试时你向 `localhost` 发送请求。现在应用了 TLS 证书，且新证书引用的是主机的真实 DNS 记录，向 `localhost` 的请求会因通用名称（CN）检查失败而被视为证书无效。应改为向生成证书时指定的地址发送请求。

> 💡 **提示**：发送请求之前，应先在客户端为根证书添加信任。如果不添加信任，必须使用 `-k` 选项让 cURL 忽略 CN 和根证书校验。

```bash
$ curl https://your.host.address:9200 -u admin:yournewpassword -k
{
  "name" : "hostname-here",
  "cluster_name" : "opensearch",
  "cluster_uuid" : "efC0ANNMQlGQ5TbhNflVPg",
  "version" : {
    "distribution" : "opensearch",
    "number" : "2.1.0",
    "build_type" : "tar",
    "build_hash" : "388c80ad94529b1d9aad0a735c4740dce2932a32",
    "build_date" : "2022-06-30T21:31:04.823801692Z",
    "build_snapshot" : false,
    "lucene_version" : "9.2.0",
    "minimum_wire_compatibility_version" : "7.10.0",
    "minimum_index_compatibility_version" : "7.0.0"
  },
  "tagline" : "The OpenSearch Project: https://opensearch.org/"
}
```

### 使用 `systemd` 将 OpenSearch 作为服务运行

本节指导你为 OpenSearch 创建一个服务并注册到 `systemd`。服务定义完成后，可以用 `systemctl` 命令启用、启动和停止 OpenSearch 服务。本节命令基于 OpenSearch 安装在 `/opt/opensearch` 的环境，请根据你的实际安装路径调整。

> ⚠️ **警告**：以下配置仅适用于**非生产环境**的测试，不推荐在生产环境使用。如果你想以 systemd 管理的方式运行 OpenSearch，应使用 RPM 发行版安装。tar 包安装没有定义特定的安装路径、用户、角色或权限，未妥善加固主机环境可能导致意外行为。

1. 为 OpenSearch 服务创建用户：

   ```bash
   sudo adduser --system --shell /bin/bash -U --no-create-home opensearch
   ```

2. 将你的用户加入 `opensearch` 用户组：

   ```bash
   sudo usermod -aG opensearch $USER
   ```

3. 将文件属主改为 `opensearch`（如果 OpenSearch 文件在其他目录，请修改路径）：

   ```bash
   sudo chown -R opensearch /opt/opensearch/
   ```

4. 创建服务文件并打开编辑：

   ```bash
   sudo vi /etc/systemd/system/opensearch.service
   ```

5. 输入以下示例服务配置（如果 OpenSearch 文件在其他目录，请修改路径引用）：

   ```ini
   [Unit]
   Description=OpenSearch
   Wants=network-online.target
   After=network-online.target

   [Service]
   Type=forking
   RuntimeDirectory=data

   WorkingDirectory=/opt/opensearch
   ExecStart=/opt/opensearch/bin/opensearch -d

   User=opensearch
   Group=opensearch
   StandardOutput=journal
   StandardError=inherit
   LimitNOFILE=65535
   LimitNPROC=4096
   LimitAS=infinity
   LimitFSIZE=infinity
   TimeoutStopSec=0
   KillSignal=SIGTERM
   KillMode=process
   SendSIGKILL=no
   SuccessExitStatus=143
   TimeoutStartSec=75

   [Install]
   WantedBy=multi-user.target
   ```

6. 重新加载 `systemd` 管理器配置：

   ```bash
   sudo systemctl daemon-reload
   ```

7. 启用 OpenSearch 服务：

   ```bash
   sudo systemctl enable opensearch.service
   ```

8. 启动 OpenSearch 服务：

   ```bash
   sudo systemctl start opensearch
   ```

9. 验证服务正在运行：

   ```bash
   sudo systemctl status opensearch
   ```

---

## 相关链接

- [OpenSearch 配置](https://docs.opensearch.org/latest/install-and-configure/configuring-opensearch/)
- [为 tar 安装配置 Performance Analyzer](https://docs.opensearch.org/latest/monitoring-plugins/pa/index/#install-performance-analyzer)
- [安装和配置 OpenSearch Dashboards](https://docs.opensearch.org/latest/install-and-configure/install-dashboards/index/)
- [OpenSearch 插件安装](https://docs.opensearch.org/latest/opensearch/install/plugins/)
- [关于 Security 插件](https://docs.opensearch.org/latest/security/index/)
