# QQTechDigest MVP

通过 OneBot 11 反向 WebSocket 监听 NapCatQQ 事件，丢弃发送者身份和原始事件，把命中的技术内容写到 `digests/YYYY-MM-DD.md`。

## 启动

```powershell
cd D:\Work\AI\Iris\work\QQTechDigest
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1
```

首次运行会生成带随机密钥的 `config.json`。健康检查地址为 `http://127.0.0.1:8765/health`，OneBot 反向 WebSocket 为 `ws://127.0.0.1:8766/onebot`。

## 安装并接入 NapCat

```powershell
# 不带账号：下载 Shell 包并写好 OneBot 默认配置
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-napcat.ps1

# 带账号：另外启动登录；账号参数只用于 NapCat 快速登录
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-napcat.ps1 -QQ 你的QQ号
```

脚本复用本机已安装的 QQ。登录需要本人在 QQ 手机端扫码或确认，这是唯一的手工步骤。建议使用只加入获授权群聊的专用账号；NapCat 属于非官方协议端，请自行确认平台规则和群成员知情授权。

NapCat Shell、下载包与登录运行态统一存放在工作区的 `tmp/QQTechDigest/napcat/`；删除后可重新运行 `setup-napcat.ps1` 下载，不进入项目源码。

## 手工验收

1. 保持 `run.ps1` 和 NapCat 都在运行。
2. 在目标群发送：`这个崩溃是资源在异步加载完成前被释放了`。
3. 等待 5 分钟，或运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 digest` 立即结算当前窗口。
4. 打开 `digests/当天日期.md`；内容中不应出现 QQ 号、昵称或群名片。

## 配置

`config.json` 可调整监听端口、允许群、静默时间和筛选阈值。`groups` 为空表示监听该账号加入的所有群；填写群号字符串数组可设白名单。

离线自检：

```powershell
python -m unittest -v test_qq_tech_digest.py
```
