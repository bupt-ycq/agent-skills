# 此用户的已验证部署

这些是不含凭据的个人默认值。每次使用仍需核实存在性和实时状态；用户新指定的目录、账号、仓库优先。

- 源项目：`https://github.com/DeppWang/youdaonote-pull`
- 项目目录：`/home/cambricon/Documents/Codex/2026-10-21/https-github-com-deppwang-youdaonote-pull/outputs/youdaonote-pull`
- 虚拟环境：项目下 `.venv/bin/python`；启动器：项目下 `run.sh`。
- 导出目录：`/home/cambricon/文档/yucongqing/有道云`
- GitHub 账号：`bupt-ycq`；仓库：`https://github.com/bupt-ycq/youdao-notes`，要求 **PRIVATE**，已用分支 `main`。
- 本机 GitHub CLI：`/home/cambricon/Documents/Codex/2026-10-21/https-github-com-deppwang-youdaonote-pull/work/bin/gh`。若此路径失效，先检查 PATH。
- 登录通过系统密钥环保存；不得复制 CLI 凭据到技能。曾出现插件账号与 CLI 账号不同，必须实时核实，不能固定假设插件是谁。
- 复用 Chrome 会话时，曾使用的 Cookie 数据库为 `/home/cambricon/.config/google-chrome/Default/Cookies`。有道桌面端目录为 `/home/cambricon/.config/ynote-desktop`，但当时它的 Cookies 表没有这三个所需字段。不要扫描无关站点或把整个浏览器数据库复制进工作区。

## 历史状态衔接

2026-10-27 已完成一次同步：云端 652 项，本地含资源 1085 个文件；远端额外有 `.gitignore`，共 1086 个文件。提交为 `2595430572844b5cc2d701bfabf5082e266a6f3a`。这些仅为历史记录，不能当成新的验证结果。

旧云端清单：`/home/cambricon/Documents/Codex/2026-10-21/https-github-com-deppwang-youdaonote-pull/work/remote-inventory.json`。

原 Git 对象库：`/home/cambricon/Documents/Codex/2026-10-21/https-github-com-deppwang-youdaonote-pull/work/github-youdao-notes`。该目录的本地 `main` 是早期原始快照，**不等于最新远端 main**；获取远端后，从实际 `origin/main` 建立新的工作区。上次发布工作区位于 `work/2026-10-27/publish`。

特别保留仓库侧 `我的资源/git命令.md` 的现有修改以及 `.gitignore`。新同步不能直接复制整个导出目录覆盖它们。

后续每次同步在上述任务目录的 `work/sync-runs/<时间戳>/` 下保存独立状态。成功后保存当前清单、本地原始快照和 GitHub 提交号，以此替代本节中的历史基线。运行目录和归档都不在上传范围内。
