# EasySearch 2.3.1 调研报告

> **合集成分**：产品调研（作用 / 架构 / 功能 / 客户端 SDK）＋ 许可与收费模型调研 ＋ CLI / UI / CRUD 功能测试
>
> **调研对象**：192.168.3.4（工单业务机，主机名 minio-node3，麒麟 V10 x86_64，Intel Pentium Gold G5420）
> **实机实例**：`/home/test/easysearch`，EasySearch 2.3.1-2903（2026-07-21 构建，JVM 21），集群名 `my-application`，端口 19200 (HTTP) / 9301 (transport)
> **调研日期**：2026-09-14
> **信息来源**：官网 easysearch.cn、官方文档 docs.infinilabs.com、报价页 infnilabs.cn/pricing、GitHub infnilabs、192.168.3.4 实机核验

---

# 第一部分：产品调研

## 1.1 一句话定位

**INFINI Easysearch**（INFINI Labs / 极限实验室出品）是一款**基于 Lucene 的国产分布式搜索引擎**，官方定位"更安全、更轻便的 Elasticsearch 替代方案"：兼容 ES API 与 SDK（业务代码零改动），默认开启安全，安装包仅约 50MB，主打信创（国产 CPU/OS/国密）适配。

## 1.2 作用（干什么用）

- 结构化/非结构化数据检索：全文检索（BM25）、向量检索（kNN + AI embedding）、地理空间检索、组合查询、多语种支持、语义分析、聚合分析
- 作为 ES 的平滑替代：兼容 ES 语法/SDK/索引存储，可基于网关无缝迁移、随时回退，向下兼容至 ES 6.x 索引
- 典型场景：日志检索、业务数据搜索（本机即用于工单检索）、AI 向量搜索底座
- 客户案例：中国移动（移动云国产化替代）、中国一汽（50+ 套集群优化）、中国人寿、东莞证券、人保等

## 1.3 系统架构

```
客户端 (REST API / Java / Python / SQL)
   │ HTTPS (默认 19200，可配 9200)
[INFINI Gateway（可选）：负载均衡 · 限流 · 查询审计]
   │
Node 1 (master+data) ◄─9301 transport─► Node 2 ◄─► Node 3
   索引 → 主分片(S) + 副本分片(SR) 分布在各节点
```

- 经典 Lucene 倒排索引 + 分片/副本分布式模型（主分片数建索引后不可改，副本提供高可用+读扩展，单分片建议 10~50GB）
- 2.x 基于新版 Lucene（带 native ZSTD 压缩后端，Lucene912ZSTDV3 codec），捆绑 JDK
- 节点角色：master / data / ingest / coordinating（2.3.1 起 UI 强制约束 coordinating 不可与其余角色混选）
- 内置模块：Security（默认开启，TLS+认证+RBAC+LDAP/AD）、CCR 跨集群复制、ILM 索引生命周期、SLM 快照生命周期、Rollup 汇总、Data Streams 数据流、Ingest Pipeline、规则引擎、可搜索快照、跨集群搜索（CCS）
- 服务 Agent：主机级 agent 管理节点（2.3.1 新增 Agent UI、API Token 管理、`infini_agent` 内置账户）
- 管理界面：内置 **Easysearch UI**（数据探索/开发工具/巡检诊断/备份/审计/安全）+ **INFINI Console**（多集群跨版本统一治理 ES/OpenSearch/Easysearch）
- 默认端口 **19200/9301**，特意错开 ES 的 9200/9300 → 本机正是靠这一点实现"老 ES 6.6.1 + EasySearch 双引擎同机共存"

## 1.4 系统功能

### 1.4.1 核心特性（官网）

| 特性 | 说明 |
|---|---|
| 轻量易用 | 安装包约 50MB，开箱即用（本机 1G 堆即可跑） |
| 内置安全 | 默认 TLS + 身份认证，LDAP/AD、RBAC、字段级脱敏、IP 黑白名单、防暴力破解、国密 SM2/SM3/SM4 |
| 全文检索 | Lucene 底座，BM25、IK 中文分词、拼音、简繁体、HanLP、NER、同义词；重写 IK 词典结构降低内存开销 |
| 向量/AI | kNN 近似最近邻、AI embedding、rank_feature；2.3.1 新增大模型供应商管理（`/_model_provider/`） |
| 聚合分析 | 桶/指标/管道聚合、Rollup、混合搜索 |
| SQL | SQL 语法查索引，含 JDBC 客户端 |
| ES 兼容 | API/SDK/生态工具/索引存储全兼容，业务代码零改动 |
| 信创适配 | CPU：龙芯/鲲鹏/飞腾/海光/兆芯/申威；OS：麒麟/统信/欧拉/深度/移动云 BC-Linux |
| 容灾 | CDC 单向主从复制 + 基于网关的异地容灾 |

### 1.4.2 2.3.1 版本亮点（2026-07-29 发布）

- 巡检 UI 大幅扩展：集群状态/模板/索引元数据/快照/运行时信息/节点诊断/插件/分片与段信息
- 服务管理 UI：节点角色强约束（coordinating 不可混选）、登录禁止 root 账户
- AI 能力：模型供应商管理 API（`/_model_provider/`，api_key 加密存储）+ UI；Access Token（`X-API-TOKEN`）程序化认证，cluster/indices 粒度授权
- 规则引擎 API：`GET /_match_rules` 规则库管理/调试
- 性能：写入与 mapping 解析热路径优化（批量索引吞吐↑）、`source_reuse` 完善
- 修复：Java 21 下 CCR 恢复 `IllegalStateException: confined`、安全集群 UI 登录失败、ZSTD 高压力 direct-memory OOM 等

## 1.5 客户端开发语言与 SDK

| 语言/方式 | 官方性 | 说明 |
|---|---|---|
| **Java** | ✅ 官方 Easysearch Java Client（Maven） | 1.0（2023-11）首发：强类型 API + Security 模块全兼容；**2.0（2024-04）完全重构**：更轻量、强类型请求/响应、阻塞+异步双模式、流式构建器、Jackson 集成、自带低级别 REST 客户端（连接池/重试/节点发现）；2.0.2（2024-08）安全依赖升级 |
| **Python** | ✅ 官方 easysearch-py | `pip install easysearch`，派生自 elasticsearch-py 7.10.1，INFINI 官方维护（github.com/infinilabs/easysearch-py） |
| **SQL / JDBC** | ✅ 官方 | JDBC 客户端 → 任何支持 JDBC 的语言（Java/C#/Go 等）都能接 |
| **ES 系 SDK 兼容** | ✅ 官方承诺 | 现有 Elasticsearch SDK **无需改代码**：ES Java client、elasticsearch-py、elastic.go、ES .NET、JS/PHP 等社区客户端均可走 REST 兼容层 |
| **REST API / curl** | ✅ | 全功能 HTTP 接口 |
| 管理端 | — | Easysearch UI（内置 Web）+ INFINI Console（多集群治理） |
| Go / C# / PHP / JS 原生客户端 | ❌ 无官方 | 走 ES 兼容 SDK 或 REST 即可 |

---

# 第二部分：许可与收费模型

## 2.1 结论（三问三答）

1. **是免费社区版吗？** ✅ 有免费社区版，**永久免费**；公共下载渠道（infinilabs.cn/download，最新 2.4.0-2963，约 53MB，免登录、无时间锁）拿到的就是社区版
2. **免费版有"N 节点"之类的安装限制吗？** ✅ **没有**。官方报价页对社区版不设任何节点数量上限；付费版按 **节点/年** 计价。"节点 ≤ 9" 是"中小企业创新加速包"（付费折扣包，<30 人企业）的**适用门槛**，不是免费版限制；网关纳管集群数三档均无限制
3. **免费版功能有限制吗？** ⚠️ 有。砍的是"高级安全 + 内核优化 + 容灾"部分（见 2.4 矩阵），核心检索/安全/信创全保留

## 2.2 许可性质：免费，但不是开源

- 协议 = INFINI EULA + 《Easysearch 授权协议》（2023-06-08 生效，极限数据(北京)科技有限公司）
- **允许**：个人或**内部商业用途**、自用备份安装（免额外费用）
- **禁止**：复制/分发/转售给第三方、逆向工程
- ⚠️ **品牌展示条款（5.1）**：厂商有权把**用户公司当案例展示**在官网/社媒（可书面通知终止）——敏感行业使用需让业务方知情
- 代码来源（NOTICE.txt）：Elasticsearch 7.10 派生（Apache-2.0 文件）+ OpenSearch security/index-management 插件代码（Apache-2.0），整体按 INFINI 专有 EULA 授权，**非开源**
- 另有**开源项目与教育机构免费许可计划**（infinilabs.cn/community）

## 2.3 收费模型（infinilabs.cn/pricing 实测）

| 档位 | 搜索引擎（Easysearch） | 网关（INFINI Gateway） | 支持服务 |
|---|---|---|---|
| **社区版** | **免费（永久）** | 免费 | 社区支持 5*8，维护期 1 年 |
| 专业版 | **¥39,800/节点/年** | ¥138,000/实例/年 | 7*24 邮件，销售顾问 |
| 企业版 | **¥46,800/节点/年** | ¥168,000/实例/年 | 7*24 邮件+IM+电话，专属顾问、优先响应、定制方案 |

- 中小企业创新加速包：<30 人且集群节点 ≤9，Easysearch+Gateway 企业版一年打包 **¥98,000**（原价 ¥421,200）
- 维护生命周期：社区版 1 年，付费版同订阅期
- 节点计费口径："节点数量 = 需部署或纳管的 Easysearch/Elasticsearch/OpenSearch 数据节点总和"

## 2.4 三档功能矩阵（官方报价页逐格核对，✓=有 ✗=无）

| 功能 | 社区版 | 专业版 | 企业版 |
|---|---|---|---|
| 安全设置 / 加密通信 / SSL 证书动态管理 / RBAC / ABAC / LDAP/AD / 文档字段级权限 / IP 黑白名单 | ✓ | ✓ | ✓ |
| 字段级脱敏 | ✗ | ✓ | ✓ |
| 防暴力破解 / 基于上下文阻断 | ✗ | ✓ | ✓ |
| 备份文件加密 | ✗ | ✗ | ✓ |
| 审计日志 | ✗ | ✗ | ✓ |
| 跨集群搜索 | ✓ | ✓ | ✓ |
| 同版本跨集群复制（CCR） | ✗ | ✓ | ✓ |
| 跨版本跨集群复制 | ✗ | ✗ | ✓ |
| 快照/恢复 API / ILM 生命周期 | ✓ | ✓ | ✓ |
| SQL 语法 + JDBC 客户端 | ✓ | ✓ | ✓ |
| IK/拼音/简繁分词插件 | ✓ | ✓ | ✓ |
| IK 分词企业版 | ✗ | ✗ | ✓ |
| 可搜索快照 / 异步搜索 | ✗ | ✗ | ✓ |
| 字段去重 / 跨索引动态关联（FakeJoin） | ✗ | ✗ | ✓ |
| kNN 向量搜索 | ✓ | ✓ | ✓ |
| Bucket 聚合熔断 / 写入查询限流 / zstd 压缩 / _source 复用 | ✗ | ✓ | ✓ |
| IPv6 | ✗ | ✓ | ✓ |
| 信创适配（申威/龙芯/飞腾/鲲鹏/海光/兆芯 + 欧拉/UOS/麒麟） | ✓ | ✓ | ✓ |
| Windows / Linux / Docker / K8s 部署 | ✓ | ✓ | ✓ |
| 技术支持 / 销售顾问 | ✗（社区 5*8） | ✓（7*24 邮件） | ✓（7*24 全渠道） |
| 专属顾问 / 优先响应 / 定制方案 | ✗ | ✗ | ✓ |

## 2.5 3.4 实机核验（2026-09-14）

- 安装包 `easysearch-2.3.1-2903-linux-arm64.tar.gz`（76MB，9/7 16:44 拷入）——**文件名标 arm64 但内容实为 x86_64**（`file` 验证 java 为 x86-64 ELF），文件名有坑，内容匹配机器
- 机器实为 **Intel Pentium Gold G5420（桌面级双核）小主机** + 麒麟 V10 x86_64，**非国产 ARM**
- **`data/` 下无任何 license 文件** → 判定为**社区版**（公共下载 + 无授权文件）；单节点部署，合规无虞
- `config/` 已初始化 TLS 全套证书（admin/ca/instance + keystore）→ 加密通信已启用
- 运维提示：若业务将来需要**限流/审计日志/CCR 容灾**，需升级专业版/企业版（按节点计费）；社区版无官方支持，只能靠社区

---

# 第三部分：CLI 工具 / 管理 UI / CRUD 功能测试

## 3.1 CLI 工具：✅ 有，全套（`/home/test/easysearch/bin/`）

| 工具 | 用途 |
|---|---|
| `easysearch` | 主启动器（`-d` 守护、`-V` 版本、`-E` 设置；`--version` 实测输出 2.3.1 / JVM 21.0.9） |
| **`easysearch-cli`** | **通用 Java CLI 入口**（小堆 64M 轻量模式，各子工具经此启动） |
| `easysearch-shard` | 分片工具（ShardToolCli） |
| `easysearch-plugin` / `easysearch-keystore` / `easysearch-node` | 插件管理 / 密钥库管理 / 节点工具 |
| `initialize.sh` / `initialize-cluster.sh` | 安全初始化（证书 + 随机 24 位强密码，密码只打印到终端不落日志） |
| `reset_admin_password.sh` / `update_password.sh` / `hash_password.sh` | 密码重置 / 修改 / bcrypt 散列 |
| `generate_certs.sh` / `generate-tlcp-certs.sh` / `install-tongsuo-local.sh` | TLS 证书生成 + **国密 TLCP（铜锁）**支持 |
| `install_plugin.sh` / `tlcp-curl.sh` | 插件安装 / 国密 curl |

官方文档另有《命令行工具参考》章节（部署手册 > 参数配置）。

## 3.2 管理 UI：✅ 有，内置 Web 控制台

- 地址：**`https://192.168.3.4:19200/_ui/`**（仅 HTTPS，自签证书，Basic 认证）
- 实测：无认证 401，带 admin 认证返回 **200 + HTML** ✅
- 功能：概览、节点/索引/分片管理、数据探索、开发工具（Dev Tools）、管道管理、规则引擎模拟、生命周期策略、备份管理、审计日志、安全管理（用户/角色/重置密码）、巡检诊断

## 3.3 CRUD 功能测试：✅ 18/18 全过

测试工具：`audit/es_crud_test.py`（Python + requests，可重复执行，finally 强制清理测试索引）
测试护栏：只用专用索引 `hq_func_test`，绝不触碰现有索引，跑完自动删除

| # | 类别 | 用例 | 结果 |
|---|---|---|---|
| 01 | 集群 | 健康检查（green, 1 节点） | ✅ |
| 02 | 增 | 创建索引 + IK mapping（ack=true） | ✅ |
| 03 | 增 | mapping 校验（ik_max_word 生效） | ✅ |
| 04 | 增 | 单文档写入 PUT _doc（result=created） | ✅ |
| 05 | 增 | `_bulk` 批量写入 ×3（errors=false） | ✅ |
| 06 | 查 | 刷新 refresh | ✅ |
| 07 | 查 | 单文档查询 GET _doc（_source 核验一致） | ✅ |
| 08 | 查 | match 中文 ik 分词查询（"工单测试" 精准 1 命中） | ✅ |
| 09 | 查 | bool(term + range) 组合查询 | ✅ |
| 10 | 查 | multi_match + 排序 + 分页（total=3, size=2） | ✅ |
| 11 | 查 | 聚合 terms(status) + avg(score) | ✅ |
| 12 | 查 | `_count`（=4） | ✅ |
| 13 | 改 | `_update` doc 更新（status 变更核验） | ✅ |
| 14 | 改 | painless 脚本自增（qty 1→11） | ✅ |
| 15 | 改 | `_update_by_query`（updated=1） | ✅ |
| 16 | 删 | 单文档 DELETE _doc（result=deleted） | ✅ |
| 17 | 删 | `_bulk` 批量删除 ×2（剩余 count=1 核验） | ✅ |
| 18 | UI | `/_ui/` 可达性（200 + HTML） | ✅ |

**测试索引清理**：`DELETE /hq_func_test` → status=200, ack=true ✅
**首跑插曲**：首跑 12/18，唯一失败根因是测试脚本自己在 `_bulk` action 里漏了 `_index` 字段（根路径 `/ _bulk` 时每条 action 必须带 `_index`），修复后 18/18 全绿。

## 3.4 测试过程中的重要发现 🔍

1. **集群 `my-application` 是空的**：仅 3 个系统索引（.security / .job-scheduler-lock / .analysis_ik），业务数据尚未迁入——EasySearch 9/7 部署至今基本闲置，而 19200/9301 全接口暴露着空集群，建议收敛暴露面
2. **admin 密码明文躺在 `/home/test/.bash_history`**（部署者 9/7 的 curl 验证命令）——建议清理 shell 历史或用 `bin/update_password.sh` 换密码
3. 集群名 `my-application` 是默认值未改（小瑕疵）
4. 中文 IK 分词实测有效，"工单测试文档一" 类中文内容检索精准

---

# 附录：原始数据与工具位置

| 文件 | 内容 |
|---|---|
| `notes/easysearch-2.3.1-research.md` | 本报告的调研底稿（含 2.3.1 完整 changelog） |
| `audit/es_crud_test.py` | CRUD 功能测试工具（18 用例，可重复执行） |
| `audit/raw/34_software_detail.txt` | 3.4 全量端口 + ps -ef 原始数据 |
| `audit/raw/34_software.txt` | 3.4 全量 rpm 清单（1473 包） |
| `/tmp/pricing_matrix.txt`（工作机） | 官方报价页功能矩阵解析缓存 |

> 注：报告遵循密码打码纪律，admin 口令未落盘明文；如需找回，参照 3.4 的 `/home/test/.bash_history` 中 9/7 的 curl 命令行，或使用 `bin/reset_admin_password.sh` 重置。
