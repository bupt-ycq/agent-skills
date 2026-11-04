# API 操作与核验

配套工具针对 Confluence Server/Data Center 常见的 REST v1 storage 工作流。Cloud、SSO 和连接器支持情况不同，先检查环境，不把接口或认证方式硬套到其他部署。

## 工具使用

脚本依赖 Python 3 和 `requests`。全局参数放在子命令前。密码支持隐藏输入或 `CONFLUENCE_PASSWORD`；令牌支持 `CONFLUENCE_TOKEN`，用 `--auth bearer`；用户名来自 `--user` 或 `CONFLUENCE_USERNAME`。不要将密码放进命令行或把环境变量值打印出来。优先使用已有授权凭据，不重复询问已有授权。

下面的 `BASE_URL`、`PAGE_ID`、`PARENT_ID` 是任务对应值，`SKILL_DIR` 是本技能目录。

```bash
python "$SKILL_DIR/scripts/wiki_api.py" --base-url "$BASE_URL" get --page-id "$PAGE_ID" --out before.json
python "$SKILL_DIR/scripts/wiki_api.py" --base-url "$BASE_URL" render --page-id "$PAGE_ID" --storage draft.storage.html --out preview.json
python "$SKILL_DIR/scripts/wiki_api.py" --base-url "$BASE_URL" probe --page-id "$PAGE_ID" --out capabilities.json
python "$SKILL_DIR/scripts/wiki_api.py" --base-url "$BASE_URL" update --before before.json --storage draft.storage.html --out after.json
python "$SKILL_DIR/scripts/wiki_api.py" --base-url "$BASE_URL" create --parent-id "$PARENT_ID" --title '页面标题' --storage draft.storage.html --out created.json
```

- `get` 保存 storage/view、version、ancestors、space。不要把本地页面快照提交到共享技能。
- `render` 做 storage → view 转换，不修改正文；结果仍需检查实际表现。
- `probe` 默认读取 `assets/macro-probes.json`；`--cases` 可指定精简探针。输出状态只是筛查，必须审阅 value/证据，不能把“需检查渲染结果”当成已经验证可用。
- `update` 读取 before 快照并比对当前 ID、版本、标题、空间和祖先链；预览成功后再次检查再 PUT。只更新同一页面正文和版本。快照包含来源 base URL，禁止混用别的站点。
- `create` 读取父页面并继承空间，显式设置 ancestors。网络超时或上次结果不明时先查询是否已创建，不立即再次调用。
- 保存后脚本回读并检查位置；正文语义、所有数据和视觉表现仍由 agent 核验。服务端可能规范化 storage，不能一律按字符串完全相等判断失败。
- 工具不自动重试写入，不自动回滚，不删除页面或附件。失败信息不打印凭据或完整服务器响应。

本地输出限制访问权限；依然只在可信目录存放快照。长期凭据存储由已授权连接器/凭据管理器负责。

## 底层接口

### 读取

`GET /rest/api/content/{id}?expand=body.storage,body.view,version,ancestors,space`

记录当前真实 ancestor ID 列表，不使用会话早期记忆假定父目录。链接可由站点 base 和 `/pages/viewpage.action?pageId={id}` 组成。

### 预览 / 能力探测

`POST /rest/api/contentbody/convert/view`

```json
{"representation":"storage","value":"<p>正文</p>","content":{"id":"目标页面或预览用父页面ID"}}
```

检查 `wysiwyg-unknown-macro`、`Unknown macro`、`Error rendering macro`、附件资源错误等。没有错误字符串仍不证明正确：图表可能方向反了，TOC 可能仅返回容器，插件可能是空壳。

宏目录接口若不可用，选择要用的几个宏逐个转换。探针使用无敏感信息的小样例。

### 更新正文

`PUT /rest/api/content/{id}`

```json
{"id":"目标ID","type":"page","title":"保持现有标题","version":{"number":8,"message":"优化排版，保留原始数据与范围说明"},"body":{"storage":{"representation":"storage","value":"生成的片段"}}}
```

version 是最新读取版本 + 1。更新不传 ancestors，避免意外迁移。409 或预检查冲突时重新读取、比较与合并；不能只把版本加一强盖他人修改。读写间的竞争仍依赖服务端版本检查。

### 创建子页面

`POST /rest/api/content`

```json
{"type":"page","title":"新文章标题","space":{"key":"父页面所属空间"},"ancestors":[{"id":"父页面ID"}],"body":{"storage":{"representation":"storage","value":"新文章正文"}}}
```

新建后验证父 ID 和空间，回读正文。不要为了新建 child 把全文追加到 parent。

### 附件（按任务需要调用）

- 查询：`GET /rest/api/content/{pageId}/child/attachment`（处理分页）。
- 上传：`POST /rest/api/content/{pageId}/child/attachment`，multipart file，`X-Atlassian-Token: no-check`。
- 同名附件可能形成新版本：先看已有附件，不默默覆盖用户资料。
- 使用返回的下载路径下载，校验字节数/哈希。不要把调试环境和凭据全量打包上传。
- 工具未封装上传，必要时通过连接器或独立小脚本执行；删除操作必须在用户授权范围内。

## 图表和图片验收

1. 从预览或保存后的 view 提取 chart 图片路径。
2. 只把认证信息发送到已授权同源站点。默认禁止自动重定向，跨域另行判断。
3. 用文件头识别 PNG/JPEG/SVG；MIME 是 `application/x-download` 但 PNG 签名正确时仍可检查。
4. 用图像工具检查中文、类别、趋势、单位、剪裁和图例。临时 URL 不能作为长期分享链接。
5. 图表宏管理自身输出；手工制作图则上传正式附件，使用 `ri:attachment`。

## 失败处理

- 401/403 或登录页：修正认证，不继续当作页面 JSON。404 也可能与未认证有关。
- 版本冲突：保留草稿与 before，重新读取后合并。
- 宏未知：换可用原生组件或附件，重新预览。
- 资源缺失：补合法附件引用或移除装饰，不能掩盖错误占位符。
- 写请求超时/响应不明：停止自动写重试，读取页面版本/正文或查询同标题 child 确认结果。
- 保存成功但验证失败：明确远端已改动，回读并做最小修正；不要把后置断言失败误报为“没保存”。
