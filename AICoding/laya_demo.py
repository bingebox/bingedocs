#!/usr/bin/env python3
"""Laya 端到端演示：
1) Python SDK：一条中文运维工单，choice + score + noul 三个问题一次前向
2) 真实 MCP stdio 会话：模拟 Hermes Agent 作为 MCP client 的完整交互
   (initialize -> tools/list -> tools/call laya_decide)
"""
import json, subprocess, sys, time, os

PY = sys.executable
print("=" * 70)
print("PART 1: Python SDK — Router.predict (choice / score / noul)")
print("=" * 70)

from laya import Router

t0 = time.time()
# 指向本地已下载的 multilingual 检查点（绕过 HF xet 下载问题）
router = Router(models={"multilingual": "/home/honya/models/laya/multilingual"},
                device="cpu")
agent = router.load("multilingual")  # 预热加载，单独计时
print(f"检查点加载耗时: {time.time()-t0:.1f}s (一次性)")
state = {
    "ticket_id": "OPS-20261001-042",
    "source": "监控告警(电话+企业微信)",
    "subject": "生产环境人脸识别服务接口超时",
    "body": (
        "【P1告警】prod-face-recognition 服务 P95 延迟从 120ms 飙到 4.2s，"
        "错误率 38%。影响：门店人脸门禁刷脸全部失败，约 2000 名员工无法打卡，"
        "部分用户已投诉。初步排查：昨晚 22:00 人脸模型热更新后出现。"
        "请求：需要立即恢复，客户现场有领导参观，业务影响重大。"
    ),
}
questions = {
    # choice：从枚举里选一个（≤20 选项）
    "queue": {
        "type": "choice",
        "instructions": "这条告警应该路由到哪个处理队列？",
        "criteria": {
            "ml_platform": "AI/人脸/模型服务故障、模型热更新问题",
            "network": "网络、DNS、负载均衡故障",
            "infra": "服务器、容器、数据库基础设施故障",
            "billing": "费用、账单、合同问题",
            "other": "以上都不是",
        },
    },
    # score：在有序量表上打分（期望等级 + 分布）
    "urgency": {
        "type": "score",
        "instructions": "这条告警的紧急程度？",
        "criteria": ["P3 低：可排期处理", "P2 中：当天处理", "P1 高：数小时内处理", "P0 紧急：立即处理，有重大业务影响"],
    },
    # noul：是/否，返回 P(true)
    "is_model_related": {
        "type": "noul",
        "instructions": "问题是否与最近的人脸模型更新直接相关？",
    },
    "needs_escalation": {
        "type": "noul",
        "instructions": "是否需要立即升级到平台负责人（有重大业务影响或管理层关注）？",
    },
}

t1 = time.time()
res = router.predict(state, questions)
dt_ms = (time.time() - t1) * 1000

print(f"路由检查点 : {res['routing']['model']}  ({res['routing'].get('reason','')})")
print(f"CPU 延迟   : {dt_ms:.0f} ms（含首次检查点加载则更长；预热后单问为毫秒级）")
a = res["answers"]
print("\n[choice] 队列归属:")
print(f"  答案 = {a['queue']['choice']}")
print(f"  分布 = " + ", ".join(f"{k}:{p:.3f}" for k, p in a["queue"]["probabilities"].items()))
print(f"  置信度 = {a['queue']['confidence']:.3f}")
print("\n[score] 紧急程度:")
print(f"  期望等级 = {a['urgency']['score']:.2f} / {len(questions['urgency']['criteria'])-1}  (0=P3 ... 3=P0)")
dist = a["urgency"].get("probabilities")
print(f"  分布 = " + ", ".join(f"{k}:{v}" for k, v in dist.items()) if isinstance(dist, dict) else f"  分布 = {dist}")
print("\n[noul] 是否模型相关:  P(true) =", f"{a['is_model_related']['noul']:.3f}")
print("[noul] 是否需升级:    P(true) =", f"{a['needs_escalation']['noul']:.3f}")

# 置信门控演示：低置信 -> 升级 LLM
gate = 0.6
if a["queue"]["confidence"] < gate:
    print(f"\n>>> 门控: 队列判断置信度 {a['queue']['confidence']:.2f} < {gate} → 应升级给 LLM(System 2) 复核")
else:
    print(f"\n>>> 门控: 队列判断置信度 {a['queue']['confidence']:.2f} ≥ {gate} → 直接执行，不调 LLM")

print()
print("=" * 70)
print("PART 2: 真实 MCP stdio 会话（Hermes Agent 视角）")
print("=" * 70)

# 官方 MCP server 入口：laya-mcp-server 控制台命令
# LAYA_MODELS 只预载 multilingual（本地路径已就位，避免去 HF 下载 english）
cmd = ["/home/honya/.venvs/laya/bin/laya-mcp-server"]
print("MCP server 命令:", " ".join(cmd))
env = {**os.environ,
       "LAYA_MODELS": "multilingual",
       "LAYA_DEVICE": "cpu",
       "HF_HUB_DISABLE_XET": "1"}
print("LAYA_MODELS =", env["LAYA_MODELS"])

def mcp_rpc(proc, method, params=None, id=1):
    msg = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        msg["params"] = params
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    # 读一行（跳过可能的通知）
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("MCP server closed stdout")
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            print("  (非JSON行:", line.strip()[:120], ")")
            continue
        if data.get("id") == id:
            return data

# 预热：让 server 先加载模型（后台完成，不阻塞演示输出）
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True,
                        env={**os.environ, "LAYA_PRELOAD": "0"})
try:
    init_resp = mcp_rpc(proc, "initialize", {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "hermes-agent-demo", "version": "0.1"},
    }, id=1)
    print("\n[1] initialize 响应:")
    print(json.dumps(init_resp.get("result", {}), ensure_ascii=False, indent=2)[:600])
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()

    tools_resp = mcp_rpc(proc, "tools/list", {}, id=2)
    tools = tools_resp.get("result", {}).get("tools", [])
    print(f"\n[2] tools/list → {len(tools)} 个工具:")
    for t in tools:
        print(f"  - {t['name']}: {t.get('description','')[:90]}")

    # 调用 laya_decide（或 laya_predict），对同一条工单发同样的三个问题
    call_tool = next((t for t in tools if t["name"] in ("laya_decide", "laya_predict")), None)
    if not call_tool:
        print("!! 未找到 decide/predict 工具")
    else:
        print(f"\n[3] tools/call → {call_tool['name']}（第一次调用含模型下载/加载，可能较慢）")
        if call_tool["name"] == "laya_decide":
            params = {"state": state, "questions": questions}
        else:  # laya_predict 可能是 (state, questions_json) 形态，按 schema 探测
            props = call_tool.get("inputSchema", {}).get("properties", {})
            print("  该工具参数:", list(props.keys()))
            params = {}
            for k, v in props.items():
                if k.lower() in ("state", "questions"):
                    params[k] = state if k.lower() == "state" else json.dumps(questions, ensure_ascii=False)
                elif k == "model":
                    params[k] = "multilingual"
        t2 = time.time()
        call_resp = mcp_rpc(proc, "tools/call", {"name": call_tool["name"], "arguments": params}, id=3)
        dt = time.time() - t2
        print(f"  (耗时 {dt:.1f}s，首次调用含检查点下载/加载)")
        result = call_resp.get("result", {})
        content = result.get("content", [])
        for c_ in content:
            if c_.get("type") == "text":
                print("  工具返回 (MCP content[0].text):")
                txt = c_["text"]
                try:
                    print("   " + json.dumps(json.loads(txt), ensure_ascii=False, indent=2)[:1800])
                except Exception:
                    print("   " + txt[:1800])
        if result.get("isError"):
            print("  !! isError:", json.dumps(result, ensure_ascii=False)[:500])
finally:
    proc.terminate()
    try:
        err = proc.stderr.read()[:2000]
        if err.strip():
            print("\n--- MCP server stderr (尾部) ---")
            print(err[-1500:])
    except Exception:
        pass
print("\n=== DEMO DONE ===")
