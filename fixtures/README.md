# 固定测试向量（Golden tests）

用固定 fixture 把行为锁死，避免上线后口径漂移。

| Fixture | 目录 | 期望 |
|---------|------|------|
| **1. Allowed** | fixture_allowed | repo_verdict=allowed, explanations_mode=NONE, explanations_top=[] |
| **2. Needs approval** | fixture_needs_approval | repo_verdict=needs_approval, explanations_mode=APPROVAL_SIGNALS_ONLY, Top3 含该 signal |
| **3. Approved** | 构造 skills_data + repo_verdict=approved | repo_verdict=approved, explanations_mode=APPROVAL_SIGNALS_ONLY, Top3 仍来自 approval signals |
| **4. Blocked** | fixture_blocked | repo_verdict=blocked, explanations_mode=OFFSEC_ONLY, Top3 仅 offsec_override |
| **Remote-pipe** | fixture_remote_pipe | 锁死产品行为：rules 规定 block-remote-pipe=Blocked；verdict=blocked，findings 含 BLOCK_REMOTE_PIPE |
| **5. Blocked 无证据** | 构造 skills_data（effective_category=offsec, findings=[]） | 生成 OFFSEC_OVERRIDE_SYNTH，全量 explanations 中 synth 含 file 锚点 |
| **6. Top3 去重** | 构造 skills_data（同 signal 同文件 2 次 + 另一 signal 另一文件） | Top3 优先不同 signal 再不同 file，多跑 hash 一致 |
| **对抗性** | apply_approval_elevation(blocked, True) | 必须仍为 blocked，用测试锁死 |

验收：`python tests/test_fixtures.py`（或 `pytest tests/test_fixtures.py`）。9 个用例全部通过方可视为 MVP 可交付试用。
