# Neko + CloakBrowser custom image

这是一个基于 `m1k1o/neko` 的 **CloakBrowser 容器化运行方案**。它将原本 `google-chrome` app 层替换为 CloakBrowser，同时保留 Neko 的 X11 / PulseAudio / WebRTC 流水线，并额外暴露 Chromium DevTools Protocol (CDP) 端口，便于自动化与调试。

## 当前完成内容

- `apps/cloakbrowser/`：CloakBrowser 运行层，复用已固定摘要的上游运行时结构
- `deploy/docker-compose.cloakbrowser.yml`：本地验证 / 单机部署 compose 文件
- `deploy/systemd/neko-cloakbrowser.service`：基于 docker compose 的 systemd 封装
- `Taskfile.yml`：标准 `task` 工作流，不依赖额外 `rtk` 包装
- `deploy/.env.cloakbrowser.example`：部署时需要复制并填写的环境变量模板

## 设计原则

这一版优先解决的是“**真的能构建、能启动、能验证**”，而不是堆一层看起来很华丽但无法落地的包装。

关键改动包括：

- **固定 `cloakhq/cloakbrowser` 与 `ghcr.io/m1k1o/neko/google-chrome` 的镜像摘要**，避免 future `latest` 漂移
- **去掉对 CloakBrowser 私有 Chromium 版本目录的硬编码**，构建时自动发现 `chromium-*` 目录
- **compose 支持自举构建**，首次 `docker compose up -d` 不再假定镜像已手工存在
- **补上 profile / downloads 持久化卷**
- **健康检查同时覆盖 CDP 与 Neko `/health`**
- **移除 README 中不真实的 Playwright 保活描述**
- **Taskfile 改为标准 `task + docker + docker compose + curl`**
- **切换为容器内 TCP 代理桥接 CDP**，避免 Docker bridge/NAT 直接转发 Chromium loopback DevTools 端口时出现 reset
- **新增一键 smoke test 任务用于回归验证**

## 前置要求

你至少需要：

- Docker
- Docker Compose（`docker compose` 子命令）
- `task`（go-task）

## 快速开始

### 当前固定的上游镜像摘要

- `cloakhq/cloakbrowser@sha256:535b228133d3efffa25fa2a50fbff47ffcee21464bd7dcb69bcdaee144cc8100`
- `ghcr.io/m1k1o/neko/google-chrome@sha256:5511a426db00c474ff15e21fcdaa3887d737f9d379080a2cd5d05bea81872fce`

### 1. 准备环境变量

```bash
cd /home/yun/workspace/neko
cp deploy/.env.cloakbrowser.example deploy/.env.cloakbrowser
```

然后编辑 `deploy/.env.cloakbrowser`，至少修改：

- `NEKO_MEMBER_MULTIUSER_USER_PASSWORD=***`
- `NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD=***`
- `CLOAKBROWSER_START_URL=https://example.com`
- `NEKO_NAT1TO1=203.0.113.10`（公网部署时）
- `CLOAKBROWSER_HOST_PROFILE_DIR=/home/yun/workspace/neko-data/profile`
- `CLOAKBROWSER_HOST_DOWNLOADS_DIR=/home/yun/workspace/neko-data/downloads`

如果你要从公网访问，还需要设置：

- `NEKO_NAT1TO1=<你的公网 IP>`

如果你希望 Hermes 和浏览器/Neko 共用同一个文件通道，保持下面这组默认值即可：

- `NEKO_FILE_TRANSFER_ENABLED=true`
- `NEKO_FILE_TRANSFER_PATH=/home/neko/Downloads`

> 注意：示例文件里的密码只是占位，**不要**直接用于生产。

### 2. 构建镜像

不需要手动 `source` 环境文件。compose 和 systemd 都会直接读取 `deploy/.env.cloakbrowser`。

```bash
cd /home/yun/workspace/neko
go-task image:build
```

### 3. 启动服务

```bash
cd /home/yun/workspace/neko
go-task service:up
```

### 4. 验证服务

检查 Neko 健康状态：

```bash
go-task service:health
```

检查 CDP：

```bash
go-task service:cdp
```

默认监听地址：

- Neko HTTP: `http://127.0.0.1:18080`
- CloakBrowser CDP: `http://127.0.0.1:19222/json/version`

> 说明：当前方案恢复为标准 bridge 网络。CloakBrowser 仍只监听容器内 `127.0.0.1:9222`，再由容器内 TCP 代理转发到 `0.0.0.0:9223`，最后映射到宿主机 `127.0.0.1:19222`。这样既保留 Neko 的原始运行拓扑，也绕开 Docker 对 loopback DevTools 端口的转发问题。

## 持久化目录

默认建议使用宿主机 bind mount，而不是 Docker named volume：

- `${CLOAKBROWSER_HOST_PROFILE_DIR}` → `/home/neko/.config/cloakbrowser`
- `${CLOAKBROWSER_HOST_DOWNLOADS_DIR}` → `/home/neko/Downloads`

推荐宿主机目录：

- `/home/yun/workspace/neko-data/profile`
- `/home/yun/workspace/neko-data/downloads`

这样会同时带来三件事：

- 浏览器 profile 持久化
- 浏览器下载内容直接落到宿主机目录
- Hermes 可以直接读写下载目录，不必绕过 Docker volume

另外，当前 compose 也默认启用了 Neko 内建文件传输：

- `NEKO_FILE_TRANSFER_ENABLED=true`
- `NEKO_FILE_TRANSFER_PATH=/home/neko/Downloads`

这意味着：

- 用户在浏览器里下载的文件会进入共享目录
- 用户通过 Neko 文件传输上传的文件也会进入同一个共享目录
- Hermes 可以直接操作 `/home/yun/workspace/neko-data/downloads` 里的文件

### 文件流使用说明

#### 浏览器下载 → Hermes 读取

浏览器中的下载文件会直接落到：

```bash
/home/yun/workspace/neko-data/downloads
```

Hermes 后续可以直接读取、重命名、上传或分析这个目录里的文件。

#### Hermes 投喂文件 → 浏览器 / Neko 使用

如果你希望把本机文件交给浏览器或 Neko 使用，只需要把文件放进：

```bash
/home/yun/workspace/neko-data/downloads
```

容器内会在下面这个路径同时看到它：

```bash
/home/neko/Downloads
```

#### 常用操作示例

查看共享下载目录：

```bash
ls -lah /home/yun/workspace/neko-data/downloads
```

把本机文件送进共享目录：

```bash
cp /path/to/local-file /home/yun/workspace/neko-data/downloads/
```

查看容器内对应目录：

```bash
docker exec neko-cloakbrowser ls -lah /home/neko/Downloads
```

如果你要用 Hermes 自动化浏览器下载，然后再由 Hermes 处理文件，推荐始终围绕这个共享目录进行，不要再走 `docker cp` 这类旁路。

## systemd 部署

这个 systemd 单元本质上只是对 docker compose 的封装。它会显式使用：

- `%h/workspace/neko/deploy/.env.cloakbrowser`

因此不需要把变量额外注入 systemd 环境。

推荐流程：

1. 先确认 `deploy/.env.cloakbrowser` 已正确填写
2. 手动完成一次 `task service:up` 验证
3. 再安装并启用 systemd

```bash
cd /home/yun/workspace/neko
sudo go-task systemd:install
sudo systemctl enable --now neko-cloakbrowser.service
```

查看状态：

```bash
sudo go-task systemd:status
```

> 说明：当前 unit 默认以 `%h/workspace/neko` 作为工作目录，因此更适合“当前用户在自己工作区部署”。如果你要做更通用的系统级安装，建议再额外做一个带 `EnvironmentFile=` 的发行版级 unit。

## 生产部署注意事项

这套 compose 文件首先面向 **本机验证 / 单机部署**。如果你要正式对外服务，必须额外处理：

- `NEKO_NAT1TO1`
- 反向代理 / TLS
- UDP 端口放通（当前示例默认使用单端口 `NEKO_WEBRTC_UDPMUX=52000`）
- 域名与外部可达性验证

如果这些没处理好，容器可以是“运行中”，但 WebRTC 依然可能无法正常工作。

## 最小验收标准

当你说“这个方案已经完成”，至少应该满足下面几点：

1. `go-task image:build` 可以成功构建镜像
2. `go-task service:up` 可以成功拉起容器
3. `go-task service:health` 返回成功
4. `go-task service:cdp` 返回成功
5. 容器内 `supervisorctl status` 中的核心进程都处于 `RUNNING`
6. 重启 compose 后浏览器 profile 仍然存在
7. `go-task verify:smoke` 可以作为一次性回归验证通过

## 已知限制

- 目前仍然依赖 `cloakhq/cloakbrowser:latest` 的内部 Python 包结构与 Chromium 缓存布局；虽然已经去掉了硬编码版本目录，但上游若大改内部组织，仍需重新适配。
- systemd 单元目前是“工作区部署”模型，不是可分发安装包级别的通用部署方案。
- 这套方案没有引入额外的 room management / multi-room orchestration，只是单实例 CloakBrowser Neko 运行层。

## 调试命令

一键 smoke test：

```bash
go-task verify:smoke
```

它会强制重建并重建容器，然后校验：

- 当前容器使用的镜像 ID 与刚构建出的 `local/neko-cloakbrowser:local` 一致
- 若 Compose 写入了镜像标签，也会顺手记录下来供排查
- `health` 返回成功
- CDP 响应里包含 `webSocketDebuggerUrl`
- `supervisorctl status` 中关键进程处于 `RUNNING`

查看 compose 状态：

```bash
go-task service:status
```

查看日志：

```bash
go-task service:logs
```

查看容器内 supervisor 进程状态：

```bash
docker exec -it neko-cloakbrowser supervisorctl status
```

查看 CDP 响应：

```bash
curl -fsS http://127.0.0.1:19222/json/version | jq
```

> 注意：返回的 `webSocketDebuggerUrl` 可能仍然是容器内原始 DevTools 地址；宿主机客户端连接时应优先使用宿主机暴露地址 `127.0.0.1:19222` 进行等价替换。

若浏览器没有起来，优先检查：

- `docker logs neko-cloakbrowser`
- `/var/log/neko/cloakbrowser.log`
- `/var/log/neko/openbox.log`
- `/var/log/neko/neko.log`

呵，这样才像一套真正能落地、而不是只会在 README 里自我陶醉的方案。