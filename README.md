# 档案片段重建台（Archive Fragment Rebuild Console）

面向档案复核员的字节片段重建工具：导入或编辑相互重叠的十六进制片段，业务 API
计算最优一致覆盖并裁决原文是否唯一；页面展示**正文十六进制、采用片段、冲突/缺口位置**。

- 前端：TypeScript + React 18 + Vite
- 后端：Python 3.11 + FastAPI（纯标准库数据结构实现求解器，无第三方求解依赖）
- 部署：多阶段 Dockerfile + Docker Compose（含健康检查、宿主机端口可配、一次性 verify 服务）

## 业务规则

- 目标正文长度 `target_length`：**1–512** 字节；片段数：**2–28**。
- 每个片段：唯一编号 `id`、零基整数偏移 `offset`、非空偶数位十六进制 `payload_hex`、
  整数可信权重 `weight`（**1–1 000 000**）。
- 片段不得越过 `target_length`；重复编号 / 格式错 / 越界一律返回 **HTTP 422**，
  错误体 `detail[].loc` 精确定位字段，如 `["body","fragments",3,"payload_hex"]`。
- **有效方案** = 一组片段，其并集覆盖目标的每一个字节，且任意重叠位置的字节相同。
- 优化：先**最大化总权重**，并列时再**最大化片段数**，响应返回这两个最优值。
- 裁决：
  - `UNIQUE` —— 所有最优方案还原同一正文；
  - `AMBIGUOUS` —— 最优方案可还原多份正文；返回按**无符号字节序**最小的两份正文
    及各自的片段见证（`witness_fragment_ids`）；
  - `IMPOSSIBLE` —— 不存在完整一致覆盖；`impossible_reason` 为
    `GAP`（区间并集盖不满，缺数据）或 `CONFLICT`（能盖满但任何完整覆盖都含冲突，数据矛盾）。

> 复核要点：**片段冲突（CONFLICT）≠ 正文歧义（AMBIGUOUS）**。
> 冲突对始终在 `conflicts` 中列出（含首个冲突位置、全部位置与双方字节）；
> 歧义指存在多份各自自洽的最优正文，数据并不矛盾。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| POST | `/api/analyze` | 提交 `{target_length, fragments[]}`，返回裁决 |

```bash
curl -s localhost:8080/api/analyze -H 'Content-Type: application/json' -d '{
  "target_length": 4,
  "fragments": [
    {"id": "A", "offset": 0, "payload_hex": "00000000", "weight": 100},
    {"id": "B", "offset": 0, "payload_hex": "ffffffff", "weight": 100}
  ]
}'
```

响应片段：

```json
{
  "status": "AMBIGUOUS",
  "optimal_weight": 100,
  "optimal_fragment_count": 1,
  "bodies": [
    {"body_hex": "00000000", "witness_fragment_ids": ["A"]},
    {"body_hex": "ffffffff", "witness_fragment_ids": ["B"]}
  ],
  "conflicts": [ {"a": {"fragment_id": "A", "offset": 0}, "b": {"fragment_id": "B", "offset": 0},
                  "first_position": 0, "positions": [0,1,2,3], "byte_a": "00", "byte_b": "ff"} ]
}
```

## 页面行为

- 编辑任意字段（含删除/新增片段）后**立即撤下旧裁决**（顶部显示“旧裁决已撤下”），
  防抖 450ms 自动重新分析；请求按序号丢弃过期响应，杜绝旧结果回闪。
- 正文十六进制：16 字节/行转储（地址 + hex + ASCII），悬停字节查看覆盖它的采用片段；
  AMBIGUOUS 时可在两份最小正文间切换。
- 覆盖轨道：采用片段绿色、未采用灰色，整列红色标记为冲突字节、斜纹为缺口。
- 422 时错误信息直接标注在对应片段/字段下方，并附完整 `loc`。

## 本地开发

```bash
# 后端
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                      # 单元/场景/400 组随机暴力对拍
uvicorn app.main:app --reload --port 8000

# 前端（另一终端）
cd frontend
npm install
npm run dev                              # 5173，/api 自动代理到 8000
```

## Docker 部署

```bash
# 宿主机端口可配置（默认 8080）
HOST_PORT=9090 docker compose up -d --build web
curl -s localhost:9090/api/health

# 一次性 verify 服务：pytest → 前端构建 → API 冒烟，自行退出，退出码报告结果
docker compose run --rm verify
echo $?        # 0 = 全部通过；非 0 = 存在失败
```

`verify` 服务等待 `web` 健康检查通过后，对容器网络内的 `http://web:8000`
执行冒烟（健康检查 + UNIQUE/AMBIGUOUS/IMPOSSIBLE/422 定位断言），
并在同一镜像内运行后端测试与真实前端构建，结束后容器退出。

不使用 Compose 时同样可手动运行：

```bash
docker build -t archive-rebuild .
docker run --rm -p 8080:8000 archive-rebuild
# 容器内一次性验收：
docker run --rm archive-rebuild bash /app/scripts/verify.sh
```

## 目录

```
backend/            FastAPI 应用
  app/main.py       路由 + 422 异常处理 + 静态托管
  app/solver.py     求解核心（冲突图上的保/删分支 DFS + 强制保留 + 剪枝）
  app/validation.py 带字段位置 loc 的输入校验
  app/models.py     Pydantic 模型
  tests/            pytest（验收四场景、422 定位、随机暴力对拍）
  scripts/smoke_api.py  API 冒烟（自带拉起服务，退出码报告）
frontend/           React + TS
  src/components/    编辑器 / 裁决 / 十六进制视图 / 覆盖轨道 / 冲突面板
scripts/verify.sh   测试 → 构建 → 冒烟 一键入口
Dockerfile, docker-compose.yml
```
