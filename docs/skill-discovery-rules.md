# Skill 发现规则（目录发现）

一个 repo 可有多个 skill；每个 skill 由**锚点文件**界定，产出 **skills[]** 列表，repo 级 verdict 由聚合得出。MVP 靠规则，不靠 AI。

---

## 1. 扫描范围（约定 skills/ + fallback）

| 阶段 | 范围 | 说明 |
|------|------|------|
| **Primary** | 只扫 **skills/** 下锚点 | 约定目录，治理成本最低 |
| **Fallback** | 若 primary 无任何 skill，则扫**全 repo** | 兼容已有结构；打 finding **SKILL_OUTSIDE_SKILLS_DIR**（needs_approval） |

**规则**：`discover_skills_with_fallback(repo_root)` 先 `find_anchors(repo_root, base="skills/")`；若为空则 `find_anchors(repo_root, base=".")` 并设 `used_fallback=True`，报告内加 repo 级 finding SKILL_OUTSIDE_SKILLS_DIR。

---

## 2. 锚点文件（Anchor）

一个 skill 必须包含一个锚点文件，用来定义“这个目录就是一个 skill”。

| 锚点 | 优先级 | anchor_type |
|------|--------|--------------|
| **skill.yaml** / skill.yml | 高 | `skill_yaml` |
| **SKILL.md** | 兼容 | `skill_md` |

**规则**：同一目录下若同时存在 skill.yaml 与 SKILL.md，以 **skill.yaml** 为准，并打 **SKILL_DUP_ANCHOR**（info）。

- **skill_root** = 锚点文件所在目录
- **path** = 锚点文件相对 repo 根的路径（未来 skill_path 审批用）

---

## 3. 发现流程（伪代码）

```
anchors = find_anchors(repo_root, base="skills/")
mode = "primary"
if anchors is empty:
  anchors = find_anchors(repo_root, base=".")
  mode = "fallback"
if mode == "fallback":
  add_repo_finding("SKILL_OUTSIDE_SKILLS_DIR", needs_approval)
if len(anchors) > 500:
  add_repo_finding("REPO_TOO_MANY_SKILLS", needs_approval); cap at 500
for anchor in anchors:
  build_skill_descriptor(anchor)  # path, root, anchor_type, id, fingerprint, findings, verdict
dedupe_by_root(skills)  # 同 root 只保留 skill.yaml
nested_pairs = find_nested_roots(skills); if any: add SKILL_NESTED_DETECTED per skill
duplicate ids: add SKILL_ID_DUPLICATE (blocked) per affected skill
```

---

## 4. 归属文件集（File Set）

单个 skill 的归属文件 = skill_root 下递归所有文件，排除上述 SKIP_DIRS。

**上限保护**：

- 单 skill 文件数 > **2000** 或 总大小 > **50MB** → finding **SKILL_TOO_LARGE**（needs_approval 或按策略 blocked）。

**Fingerprint**：对归属文件集（按路径排序后内容）做 SHA256，用于 registry/去重/审计。

---

## 5. 元数据提取

| 来源 | 字段 |
|------|------|
| **skill.yaml** | id, title, category, version, entrypoint（优先） |
| **SKILL.md** frontmatter | skill_id → id, title, category, version |
| **路径派生** | id = repo_slug + ":" + skill_root.name；title = skill_root.name；category = unknown |

---

## 6. Repo 级 verdict 聚合

对每个 skill 先算 skill.verdict，再聚合：

- 任一 skill **blocked** ⇒ **repo blocked**
- 否则任一 skill **needs_approval** ⇒ **repo needs_approval**
- 否则 **allowed**

不做分数，只做门禁策略。

---

## 7. skills[] 输出（MVP 必备）

每个 skill 至少输出：

| 字段 | 说明 |
|------|------|
| path | 锚点文件相对 repo 的路径 |
| root | skill_root 相对 repo 的路径 |
| anchor_type | `skill_yaml` \| `skill_md` |
| id / title / category / declared_version | 元数据 |
| fingerprint | `{ algo: "sha256", value: "..." }` 可复现 hash |
| findings[] | file + line_start / line_end + match |
| verdict | { status: allowed \| needs_approval \| blocked } |

---

## 8. 边界与硬规则

| 规则 | 条件 | finding | verdict |
|------|------|--------|--------|
| 单 skill 过大 | 文件数 > 2000 或 总大小 > 50MB | SKILL_TOO_LARGE | needs_approval |
| 全 repo 过多 | anchors 数 > 500 | REPO_TOO_MANY_SKILLS | needs_approval，cap 500 |
| 重复 id | 同一次扫描内重复 skill id | SKILL_ID_DUPLICATE | **blocked** |
| skill.yaml 缺字段 | 缺 id / category / version | SKILL_YAML_INVALID | needs_approval |
| 同目录双锚点 | 既有 skill.yaml 又有 SKILL.md | SKILL_DUP_ANCHOR | info |
| 嵌套 skill | 某 skill_root 在另一 skill_root 下 | SKILL_NESTED_DETECTED | needs_approval |
| 锚点在 skills/ 外 | fallback 模式 | SKILL_OUTSIDE_SKILLS_DIR | needs_approval（repo 级） |

**Fingerprint 可复现**：路径排序后，逐文件 `sha256(path + "\\0" + sha256(content))` 再合并 hash。

---

## 9. skill.yaml 最小规范（推荐客户使用）

```yaml
id: "org/ad-attack"
title: "活动目录攻击"
category: "offsec"
version: "1.1"
entrypoint: "SKILL.md"
```

后续做 registry/打包时，id、version、entrypoint 必用。
