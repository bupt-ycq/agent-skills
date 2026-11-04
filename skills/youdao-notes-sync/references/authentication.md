# 账号与登录

## 有道 Cookie

先用已有项目配置做根目录接口验证；不打印请求 URL 中的 `cstk`、Cookie 值或完整异常响应。只有真实返回包含 `fileEntry.id` 才算登录成功，读取 JSON 文件本身不代表有效。

只有在用户已授权复用本机登录状态时，才读取对应站点会话。授权在当前会话已明确时不重复询问。优先查看所指定浏览器/客户端是否存有所需项，不搜索其他站点凭据。

此部署需要按顺序写入 `YNOTE_CSTK`、`YNOTE_LOGIN`、`YNOTE_SESS`，每项为 `[名称, 本机值, ".note.youdao.com", "/"]`，顶层 JSON 为 `{"cookies": [...]}`。

Linux Chrome 的此类数据库可用 `scripts/import_chrome_cookies.py --database <明确的Cookies文件> --output <项目/cookies.json>`。用系统 Python 执行（需要 `dbus` 与 `cryptography`）；它只查询 `.note.youdao.com` 的这三项，读取 Chrome 专用密钥，校验域名摘要，原子写入 `0600` 文件，不输出值。不复制数据库、不保存解密密钥、不读取密码库。

脚本针对本次实测的 Linux v10/v11 AES-CBC 格式。若没有唯一的未锁定 Chrome 密钥、版本变化或域名校验失败，停止该自动路径，请用户通过已登录网页版的开发者工具在本地填写三项。不要试错解密其他浏览器密钥，也不要要求把 Cookie 发进聊天。

## 验证有道

从项目目录用项目解释器实例化 `YoudaoNoteApi`，`login_by_cookies()` 后读取根目录。为请求设置连接/读取超时，检查 HTTP 状态；只报告成功/状态码/错误类别。只配置登录时，不调用全量导出。

## GitHub

插件、浏览器和本机 `gh` 是独立登录状态。对实际要执行推送的通道确认身份；插件连接错误账号时使用已授权的 CLI 或让用户连接正确账号，不把笔记上传到错误账号。

`gh auth status` 在禁网沙箱中可能报告令牌无效。先取得该次正常网络访问权限并复核，只有真实失败才重新登录。身份核验使用 `gh api user --jq .login`；仓库核验使用 `gh repo view OWNER/REPO --json nameWithOwner,isPrivate,defaultBranchRef`。

需要登录时启动 `gh auth login --hostname github.com --git-protocol https --web`，使用该进程刚产生的设备码。官方链接单独写为 [GitHub 设备授权](https://github.com/login/device)，避免中文逗号等被拼进 URL。继续 CLI 的 Enter 提示以开始轮询，并让用户在目标账号下确认最终权限页面。不要复用已取消/过期设备码，不自建 PAT，不输出 OAuth 令牌。

网页显示账号首页仅证明浏览器登录；`gh` 接收到授权后，仍须用 API 核验具体账号。遇到请求暂停就停止当前登录/上传操作，不因后来“已授权”自动恢复先前被暂停的笔记推送。
