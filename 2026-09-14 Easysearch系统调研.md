---
tags: [技术, 搜索引擎, Easysearch, OpenSearch, 向量检索, ES替代, 信创]
星期: 星期一
categories: [tech]
---

# Easysearch 系统调研

> 调研对象：INFINI Labs（极限科技）出品的 **Easysearch** —— 基于 Lucene 的国产分布式搜索引擎，
> 定位"ES 国产替代"，兼容 ES 7.x API/DSL/SDK。重点评估其作为**截图多模态智能检索系统**检索层的
> OpenSearch 2.19 替代/补充方案是否成立。
>
> **关联阅读**：
> - [截图多模态智能检索系统技术调研](OCR/2026-08-23%20截图多模态智能检索系统技术调研.md)（原 OpenSearch 选型依据、索引设计、以图搜图效果评估）
> - [OCR开源模型与开源系统调研](OCR/2026-09-02%20OCR开源模型与开源系统调研.md)
> - [OpenCV+Milvus vs 商业人脸识别-1比N 检索能力技术对比方案](OpenCV%2BMilvus%20vs%20商业人脸识别-1比N%20检索能力技术对比方案.md)
> - [opensearch安装指南](opensearch安装指南.md)

## 1. 总体结论

**Easysearch 是一款工程完成度较高的国产 ES 替代方案，能力面（全文 + 向量 + 聚合 + 安全 + 信创适配）
覆盖我们截图检索系统的全部需求，技术上可作为 OpenSearch 2.19 的备选；但它不是"免费开源"，
官方明确采用**商用友好协议**（非 Apache-2.0，闭源发行 + 官网注册下载），社区生态、第三方基准、
公开 issue 渠道都远小于 OpenSearch/ES。

**结论：默认维持 OpenSearch 2.19 不变，仅当以下任一条件成立时切换评估 Easysearch：**
1. 项目落入**信创/自主可控硬约束**（要求国产 CPU/OS 适配、国密、等保）——这是 Easysearch 的独门优势；
2. 需要**原厂中文支持服务**（迁移、调优、1V1 响应）且预算允许；
3. OpenSearch 2.x 在实际运维中出现其不解决的痛点（JVM 调优、插件生态）。

三者都不成立时，为换一个搜索引擎付出的迁移成本 + 生态收窄风险 > 收益。

## 2. 基本信息与许可证（关键风险项）

| 项 | 内容 |
|---|---|
| 厂商 | INFINI Labs / 极限科技（北京，双软企业，ISO27001 等认证） |
| 最新稳定版 | **2.4.0（2026-09-10 发布）**，Lucene 9.12.2 内核（2.0.0 起） |
| 定位 | 轻量级（安装包约 50MB）、自主可控、ES 国产替代 |
| **许可证** | **商用友好协议（非 OSI 开源协议）**。官网表述："采用商用友好协议，企业可自由部署、二次开发和商业化，无协议合规风险"。未见公开的 LICENSE 全文/版本号，GitHub 上无引擎源码仓库（只有客户端、控制台、helm 等周边开源件） |
| 获取渠道 | 官网 easysearch.cn 下载 / `curl -sSL http://get.infini.cloud \| bash` 一键安装 / Docker 镜像 `infinilabs/easysearch` |
| 周边生态（开源） | easysearch-py（Python 客户端，派生自 elasticsearch-py 7.10.1，MIT 系）、INFINI Console（监控告警）、INFINI Gateway（Golang 搜索网关）、image-search-demo（以图搜图示例） |
| 商业服务 | ES→Easysearch 迁移技术支持、1V1 客户服务、企业版（国密、字段级脱敏、审计等白金版能力） |

### 2.1 许可证口径（多源交叉核查结果）

- 官网 easysearch.cn 与官方文档（docs.infinilabs.com）均写"**商用友好协议**"，承诺可自由部署/二开/商用；
- **未在任何公开渠道找到协议全文**（GitHub 无引擎仓库、官网 /license 页 404）；
- 同厂周边产品口径不一：easysearch-py 客户端标注 INFINI Labs 版权 + 开源许可，helm-charts 等标 MIT/Apache。

**风险判定：中**。比 Elasticsearch 的 SSPL/AGPL 三选一要友好（厂商主动背书"无协议合规风险"且有
一汽/移动云/人保等国内大客户背书），但**协议文本不公开 = 法务无法留档**。商用前需：
1. 向厂商索取协议全文并走内部法务评审；
2. 书面确认"闭源二次开发分发""对外提供服务"两个场景均不触发额外授权费；
3. 确认是否区分社区版/企业版功能（国密、脱敏、LDAP 高级功能疑似企业版专属，见官网对比表）。

> 对比：OpenSearch 是 Apache-2.0 + Linux 基金会治理，协议风险为零。若本项目不触发信创要求，
> 仅凭许可证一条 Easysearch 就不占优。

## 3. 能力面盘点（对照截图检索系统需求）

### 3.1 版本与演进线（官方 release notes 核实）

| 版本 | 日期 | 关键变化 |
|---|---|---|
| 1.0.0 | 2023-04 | 兼容 ES 7.x，security 模块（TLS+认证），轻量内核 |
| 1.1.0 | 2023-05 | Lucene 8.11.2，ZSTD codec，ILM |
| 1.2.0 | 2023-06 | SLM、**跨集群复制 CCR** |
| 1.4.0 | 2023-07 | **kNN 插件**：`knn_dense_float_vector` / `knn_sparse_bool_vector`、`knn_nearest_neighbors` API、LSH + exact 双模型 |
| 1.6.2 | 2023-12 | SQL 插件（REST + JDBC），SQL 可嵌全文检索 |
| 1.7.1 | 2024-03 | **快照搜索 Beta**（直接查对象存储里的备份，省存储成本） |
| 1.8.0 | 2024-04 | 写入限流（节点/分片级） |
| 2.0.0 | 2025-11 | **Lucene 升级 9.12.2**；内置 UI 插件（不再依赖第三方管理）；文本嵌入模型集成 + 语义检索 API；**搜索管道（search pipelines）**、多模型集成（OpenAI / **Ollama 本地模型**）；IK reload API |
| 2.1.1 / 2.1.2 / 2.2.0 / 2.3.0 / 2.3.1 | 2026-03~08 | 稳定性修复、插件开发文档、UI 改进 |
| **2.4.0** | **2026-09-10** | **原生 HNSW 向量搜索**：内置 `dense_vector` + Lucene HNSW，**无需 kNN 插件**；1–4096 维 float，cosine / dot_product / l2_norm / max_inner_product；query-level `knn` + 顶层 `knn`；**验证兼容 ES 8.19.17 客户端行为**（Java 8.19.17 / Python 8.19.3，需开 API 兼容模式）；不支持 int8_hnsw 等量化向量类型 |

### 3.2 需求对照表

| 截图检索系统需求 | Easysearch 匹配度 | 说明 |
|---|---|---|
| 中文全文检索（OCR 文本） | ✅ 强 | **内置** IK / jieba / hanlp / 拼音 / 简繁体（stconvert）分词器，官方口径"本地优化的中文分词"，无需像 OpenSearch/ES 那样装 analysis-ik 插件 |
| 三套向量空间（人脸 512d / DINOv2 768d / SigLIP2 768d） | ✅ | 2.4.0 原生 `dense_vector` + HNSW，支持 1–4096 维，多索引/多字段隔离（与我们"不同语义空间不混字段"的设计一致） |
| 以图搜图（kNN + 预过滤） | ✅ | 原生 `knn.filter` 是**预过滤**（filter 进 HNSW 搜索过程，非 post-filter），优于旧 kNN 插件的 post-filtering 语义；`num_candidates` 上限 10000 |
| 以文搜图 | ✅ | 查询侧算文本向量 → knn；2.0+ 还内置 text-embedding 摄取处理器（可接 **Ollama 本地模型**，离线环境可用，这点和我们有内网 LLM 的环境很合拍） |
| 混合检索（车牌文本 + 图像向量） | ✅ | 搜索管道 `hybrid_ranker_processor`（RRF，rank_constant 可调，默认 60）+ `semantic_query_enricher`；同请求内 `bool`+`knn`+`match` 复合查询也支持 |
| 车牌 keyword 精确检索 | ✅ | 标准 ES 语义 keyword/term/terms |
| 百万~千万文档 / <150GB | ✅ | 分布式集群（协调/数据/主节点）、Shard 级限流、ILM/SLM/CCR/rollup/TSDB、快照搜索（冷数据直接查 S3/MinIO 备份） |
| 安全/RBAC/审计（人脸合规） | ✅ 强 | security 默认启用（TLS+认证），LDAP，角色权限；白金版有审计、字段级脱敏、国密、防暴破——**比 OpenSearch security 插件的免费能力多**（但部分功能疑似企业版付费） |
| 信创/国产环境 | ✅ **独有优势** | 官方适配龙芯/兆芯/鲲鹏/飞腾 + 麒麟/统信，逐平台安装文档齐全；国密算法支持（企业版） |
| 运维工具链 | ✅ | 内置 UI 插件（2.0+）+ INFINI Console（多集群监控/告警/devtools）+ Gateway；比 OpenSearch Dashboards 轻量，但图表/生态不如 Dashboards |
| SQL 查询 | ✅ | SQL 插件 + JDBC 驱动（1.6.2+），可嵌全文检索 |

### 3.3 关键 API 形态（2.4.0 原生 HNSW，官方文档示例）

创建索引（与 OpenSearch `knn_vector` 的写法**不同**，是 ES 8.x 风格）：

```json
PUT /visual
{
  "mappings": {
    "properties": {
      "vis_id":   { "type": "keyword" },
      "type":     { "type": "keyword" },
      "shot_fid": { "type": "keyword" },
      "model":    { "type": "keyword" },
      "embedding": {
        "type": "dense_vector",
        "dims": 768,
        "element_type": "float",
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}
```

> 注意：2.4.0 要求 mapping 显式写 `dims` 和 `index: true`；省略 `index_options` 时默认
> `hnsw(m=16, ef_construction=100)` 并在响应中回显。

knn 查询（ES 8.x 风格，query-level）：

```json
POST /visual/_search
{
  "size": 10,
  "query": {
    "knn": {
      "field": "embedding",
      "query_vector": [0.21, -0.08, ...],
      "k": 10,
      "num_candidates": 100,
      "filter": [
        { "term": { "type": "vehicle" } },
        { "term": { "model": "dinov2" } }
      ]
    }
  }
}
```

RRF 混合检索管道：

```json
PUT /_search/pipeline/rrf-pipeline
{
  "rerank_processors": [
    { "hybrid_ranker_processor": {
        "combination": { "technique": "rrf", "rank_constant": 60 } } }
  ]
}
```

安装（对比我们的 OpenSearch tar 流程）：

```bash
curl -sSL http://get.infini.cloud | bash -s -- -p easysearch
cd /data/easysearch && bin/initialize.sh -s
chown -R easysearch:easysearch /data/easysearch
su easysearch -c "/data/easysearch/bin/easysearch -d"
```

也支持 Docker / Docker Compose / Helm（`infinilabs/easysearch` chart，需 cert-manager，初始密码复杂度要求）/ 信创平台 / 阿里云、AWS、腾讯云。

## 4. 与 OpenSearch 2.19 / Elasticsearch 对比（更新 §5.1 候选表）

| 维度 | **Easysearch 2.4** | OpenSearch 2.19 | Elasticsearch 8.x |
|---|---|---|---|
| 许可证 | 商用友好协议（**不公开**，闭源发行） | Apache-2.0 | AGPL-3.0/SSPL/ELv2 |
| 治理/背书 | 单一商业厂商（INFINI Labs） | Linux 基金会 + AWS | Elastic（半闭源化） |
| ES 兼容 | 兼容 ES 7.x API/SDK；2.4.0 验证 ES 8.19 客户端（需兼容模式）；可向下兼容 ES 6.x 索引 | 兼容 ES 7.10 系 | 本体 |
| 向量 | 原生 HNSW（Lucene 9.12，float，≤4096d）；旧 LSH 插件并存；**无 int8/PQ 量化** | Lucene HNSW + **Faiss**（IVF/HNSW、SQ/PQ 量化、GpuVector 实验） | Lucene 深度优化 + int8/BBQ 量化 |
| 混合检索 | 搜索管道 RRF（2.0+） | 原生 `rank: rrf` | 原生 RRF |
| 中文分词 | **内置** IK/jieba/hanlp/拼音/简繁 | analysis-ik 插件（需安装） | 同需 IK 插件 |
| 信创适配 | ✅ 官方逐平台适配 + 国密（企业版） | ❌ | ❌ |
| 企业级安全 | 内置，白金版含审计/脱敏/国密（部分付费） | security 插件免费全量 | X-Pack 分层付费 |
| 运维工具 | 内置 UI + Console + Gateway（同厂闭环） | Dashboards + 插件 | Kibana |
| 特色 | 快照搜索（冷数据直查）、存算分离、离线建索引、CCR、写入限流 | ML Commons、anomaly detection | 生态最全 |
| 社区/资料 | 中文文档完善（docs.infinilabs.com）；国际社区小 | 国际社区大 | 最大 |
| 第三方基准 | 无公开基准 | MLPerf 等 | 官方基准（vendor） |

### 4.1 迁移成本（如果切换）

- API 层：业务代码基本零改（兼容 ES 7.x 客户端；easysearch-py 直接可用）；
- **索引层不通用**：OpenSearch 的 `knn_vector` mapping 与 Easysearch 的 `dense_vector`/`knn_dense_float_vector` 不兼容，**已有 OpenSearch 索引不能直接搬**，只能重建重刷（文本可走快照还原到 ES 兼容格式，向量必须重新 bulk）；
- 我们目前是**项目前期（还没建索引）**，切换成本最低的窗口就是现在——PoC 阶段用哪个都是零沉没成本。

### 4.2 决策矩阵

| 条件 | 选择 |
|---|---|
| 纯内部系统、无信创要求、团队熟悉 ES/OS | **OpenSearch 2.19**（许可证零风险 + 生态 + Faiss/量化留手） |
| 有信创/自主可控要求（国产 CPU+OS、国密、等保） | **Easysearch**（唯一有官方逐平台适配 + 国密的选项） |
| 需要原厂中文服务/迁移支持且预算允许 | Easysearch（商业版） |
| 未来可能对外商业化产品 | OpenSearch 优先（协议可留档）；Easysearch 需先拿到协议全文过法务 |

## 5. 风险与缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| 协议不公开，法务无法留档 | 中 | 索取协议全文；确认二开/分发/对外服务无附加费；写入采购合同 |
| 单厂商依赖（无基金会治理），公司经营异常即停更 | 中 | 数据面是 ES 兼容 API + 快照，保留随时迁回 ES/OS 的通道；PoC 阶段保持"引擎可换"的抽象层 |
| 向量能力弱于 ES 8.x（无 int8/PQ 量化，无 Faiss/IVF） | 中（当前规模低） | 百万~千万向量 float HNSW 足够（参考旧文档 §3.7 容量评估 <150GB）；超 5000 万向量再评估量化/拆分，届时 OpenSearch 更从容 |
| 无公开性能基准与压测数据 | 低 | PoC 里加一轮压测对比（同数据同查询，Easysearch vs OpenSearch，见下） |
| 功能边界不清（哪些是企业版付费） | 中 | 向厂商确认免费边界：快照搜索、CCR、search pipeline、Ollama 集成是否社区版可用 |
| 文档质量参差 | 低 | 核心 API 有逐条中文文档 + ES 8.19 兼容说明写得清楚，实测为准 |

## 6. PoC 验证计划（若进入对比验证，1 周）

前置：与 OpenSearch 2.19 单节点**并行**跑，同数据同查询。

1. **D1**：Docker 起 Easysearch 2.4.0 单节点（`infinilabs/easysearch:2.4.0`，security 先关便于调试）+ INFINI Console 对接，验证内置 UI；
2. **D2**：建三索引（shots/faces/visual，mapping 按 §3.3 改写），灌 1 万条样例文档（含真实截图产出的向量）；
3. **D3**：跑三类查询（中文全文 + 车牌 keyword、以图搜图 knn+filter、RRF 混合），记录 P95 延迟与 recall@10；对照 OpenSearch 同组查询；
   - 通过标准：全文 P95 < 100ms；knn 百万级 P95 < 50ms；RRF 结果与 OpenSearch 版相关性人工评审无显著差异；
4. **D4**：验证 ES 7.x 客户端 + easysearch-py 直连、快照备份/恢复、IK 中文分词质量（同一批 OCR 文本的召回对比）；
5. **D5**：出对比报告（性能/召回/运维体验/免费功能边界）→ 决策是否切换。

**切换触发条件（再次明确）**：仅当 §4.2 的信创要求出现，或 PoC 显示 OpenSearch 有实质短板时切换；
否则维持 OpenSearch 2.19 原方案，Easysearch 存档为备选。

## 7. 下一步 checklist（需拍板）

- [ ] **是否触发信创要求**？（决定 Easysearch 是否进入正式候选）
- [ ] 是否向 INFINI Labs 索取协议全文 + 免费/企业版功能边界清单？
- [ ] 是否安排 1 周 PoC 对比（§6）？还是直接维持 OpenSearch 不再投入？

## 附：信息来源

- 官网：easysearch.cn（定位、迁移方案、客户案例、功能对比表）
- 官方文档：docs.infinilabs.com/easysearch（v2.4.0，含原生 HNSW、多模态搜索、语义搜索、混合搜索、信创安装指南）
- Release notes：docs.infinilabs.com/easysearch/v2.3.1 → v2.4.0（版本线核实）
- GitHub：infinilabs 组织（easysearch-py 客户端、INFINI Console、Gateway、image-search-demo、helm-charts）
- 知乎/智能体社区文章：《搜索百科（5）：Easysearch — 自主可控的国产分布式搜索引擎》（二手资料，仅参考）
