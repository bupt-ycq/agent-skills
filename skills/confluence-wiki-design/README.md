# Confluence Wiki Design

一个可复用的 Codex skill：为 Confluence Wiki 选择合适的布局与宏，通过 REST API 预览、发布并核验结果。

支持中文文档工作流，适合实验报告、技术设计、操作手册、项目周报和知识库导航页。

## 包含什么

- **宏指南**：原生布局、panel、提示框、status、目录、折叠、代码、表格、chart，以及插件宏的适用场景和 storage 示例。
- **排版方案**：信息层级、配色、摘要卡、表格高亮、可见风险与折叠详情。
- **兼容性证据**：一个 Confluence Server 7.4.5 实例的实测记录，区分实际渲染、仅识别、资源依赖和不支持。
- **可改写模板**：实验报告 storage 模板和 16 组最小宏探针；演示数字不能作为真实数据发布。
- **API 工具**：读取、预览、能力探测、新建子页面和更新，包含版本检查及保存后回读。

## 安装

将仓库放到 Codex 的技能目录中。若目标目录已存在，请先检查已有内容，不要覆盖本地修改。

```bash
git clone https://github.com/bupt-ycq/confluence-wiki-design.git "${CODEX_HOME:-$HOME/.codex}/skills/confluence-wiki-design"
```

API 工具依赖 Python 3 和 requests；使用独立虚拟环境即可：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 使用

向 Codex 提出：

> 使用 $confluence-wiki-design 美化这个 Wiki：[页面链接]。保留数据、来源和限制说明。

> 使用 $confluence-wiki-design，在这个页面下新建一篇实验报告：[父页面链接]。

> 使用 $confluence-wiki-design，通过 API 看看这个站点支持哪些排版和宏，先不要修改页面。

技能入口是 [SKILL.md](SKILL.md)。更多资料：

- [组件选择与 storage 示例](references/macros.md)
- [五类页面排版方案](references/design-patterns.md)
- [API 使用流程](references/api-workflow.md)
- [已验证实例兼容性记录](references/verified-server-profile.md)

## 单独使用 API 工具

```bash
python scripts/wiki_api.py --help
python scripts/wiki_api.py --base-url https://wiki.example.com --user YOUR_USER get --page-id 12345 --out before.json
```

默认隐藏输入密码；也支持 CONFLUENCE_USERNAME / CONFLUENCE_PASSWORD，或通过 --auth bearer 使用 CONFLUENCE_TOKEN。不要把凭据放进命令行、页面或 Git 仓库。

工具面向 Confluence Server/Data Center 常见 REST v1 storage 接口。其他部署和 SSO 需要核对接口与认证方式。插件支持取决于站点，HTTP 200 不表示宏正确渲染；图表仍需查看实际图片。网络写入超时后应先检查远端状态，不盲目重试。

页面快照和 API 输出请保存在仓库外或已忽略的 .local/ 目录。

## 验证范围

技能结构校验通过，模板与 16 组探针通过本地 XML 结构检查；API 工具经过 10 项模拟测试，覆盖版本冲突、子页面位置、未知宏、重定向和写入后回读失败。站点兼容记录来自先前的实际 API 验证，不意味着每个新站点都已验证。

公开仓库不包含账号密码、私人页面内容、页面 ID 或内网站点地址。
