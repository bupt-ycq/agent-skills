# Agent Skills

三个中文工作流技能：知乎文章发布、Confluence Wiki 排版、有道云笔记备份与私有仓库同步。

| Skill | 用途 | 入口 |
| --- | --- | --- |
| `zhihu-publish` | 整理文章、公式和图解，排版到知乎，保存草稿或发布并核验 | [SKILL.md](skills/zhihu-publish/SKILL.md) |
| `confluence-wiki-design` | 选择 Wiki 布局与宏，通过 REST API 预览、保存和回读检查 | [SKILL.md](skills/confluence-wiki-design/SKILL.md) |
| `youdao-notes-sync` | 导出有道云笔记与资源，检查增量，保留已有修改并同步到私有仓库 | [SKILL.md](skills/youdao-notes-sync/SKILL.md) |

## 安装

可以把下面这段话发给 Codex：

```text
请从 https://github.com/bupt-ycq/agent-skills 安装这三个 skill：
skills/zhihu-publish
skills/confluence-wiki-design
skills/youdao-notes-sync
如果本机已经安装，请先检查差异，保留个人配置和本地修改。
```

也可以克隆仓库，再把 `skills/` 下需要的文件夹复制到 `${CODEX_HOME:-$HOME/.codex}/skills/`。安装后应是 `skills/zhihu-publish/SKILL.md` 这样的结构；不要把整个合集作为单个 skill。已有同名目录时先比较，不直接覆盖。新会话中调用对应技能。

## 使用

### 知乎

```text
使用 $zhihu-publish，把这份材料整理成知乎文章并发布：[链接或正文]。
要求：中文自然、逻辑清楚、公式完整、关键步骤逐步推导，配有用的图解。
预览检查完成后直接发布，返回文章链接和本地备份。
```

如果需要先审稿，把发布要求改成“先给我审稿，暂不发布”。浏览器会话需要已登录；登录失效时，在实际操作的知乎页面完成扫码。Skill 记录了 Markdown 图片、表格公式及懒加载的实测处理方法，但不会让未知页面永久绑定旧选择器。

### Wiki

```text
使用 $confluence-wiki-design 美化这个 Confluence 页面：[链接]。
保留原始数据、引用和限制说明，预览后保存并核验。
```

支持布局、面板、状态、目录、折叠、代码、表格和图表；插件宏是否可用取决于站点。Python API 工具依赖见 [requirements.txt](skills/confluence-wiki-design/requirements.txt)，详细说明见[技能文档](skills/confluence-wiki-design/README.md)。

### 有道云

```text
使用 $youdao-notes-sync，把有道云最新内容备份到本地，并同步到我的 GitHub 私有仓库。
本地目录：[目录]
目标私有仓库：[OWNER/REPO]
保留本地和仓库侧已有修改，核对图片、附件与增量结果。
```

有道云 skill 基于 [DeppWang/youdaonote-pull](https://github.com/DeppWang/youdaonote-pull)，本仓库包含辅助工作流和脚本，不包含该导出器源码。首次使用按技能里的安装说明部署。登录配置保存在本机；只有用户授权后才复用指定浏览器的有道会话。

## 目录

```text
skills/
├── zhihu-publish/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   └── references/browser-workflow.md
├── confluence-wiki-design/
│   ├── SKILL.md
│   ├── agents/
│   ├── assets/
│   ├── references/
│   └── scripts/wiki_api.py
└── youdao-notes-sync/
    ├── SKILL.md
    ├── agents/
    ├── references/
    └── scripts/
```

## 数据与授权范围

这是公开的技能仓库，不是笔记备份仓库。账号凭据、Cookie、私人笔记、页面快照、机器路径和运行状态均应保存在仓库之外。个人配置可参考[有道云配置示例](skills/youdao-notes-sync/references/local-profile.example.md)。

安装技能不会自动发布文章、修改 Wiki 或上传笔记；每次执行以当次用户要求为准。有道云内容的上传目标必须核实为私有仓库。知乎发布后的转发、私信等属于额外操作。

## 来源与验证

- Wiki 技能从 [bupt-ycq/confluence-wiki-design](https://github.com/bupt-ycq/confluence-wiki-design) 的 tree `5bd813952bdf0e823ff99a9797ab8d9afa1d0701` 整理到本仓库，原仓库保留。
- 知乎技能源自一次含公式、图解的真实文章发布流程；有道云技能源自已有备份同步流程。经验中的日期、版本和数量只描述历史验证，不代表新环境已经验证。
- 有道云的本地模拟回归测试：`PYTHONDONTWRITEBYTECODE=1 python3 skills/youdao-notes-sync/scripts/test_sync.py`。该测试不联网、不读取真实账号；加密格式测试需要 `cryptography`。
