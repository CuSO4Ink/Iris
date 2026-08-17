# 安装 RenderDoc VFX Breakdown Skill

项目中的标准 Skill 位于：

```text
skills/renderdoc-vfx-breakdown/
```

分发包位于：

```text
skills/dist/renderdoc-vfx-breakdown.zip
```

修改 Skill 后，可重新生成分发包：

```text
python skills/package_renderdoc_vfx_breakdown.py
```

## 通用安装

将完整的 `renderdoc-vfx-breakdown` 文件夹复制到目标 AI 平台配置的 Skills 根目录。安装后必须保留以下相对结构：

```text
renderdoc-vfx-breakdown/
├── SKILL.md
├── agents/openai.yaml
└── references/*.md
```

不要只复制 `SKILL.md`，否则工作流、证据标准和质量门禁引用会丢失。

## 使用安装脚本

```text
python skills/install_renderdoc_vfx_breakdown.py --target-root <平台的 Skills 根目录>
```

目标中已经存在同名 Skill 时，脚本默认拒绝覆盖。需要替换时使用：

```text
python skills/install_renderdoc_vfx_breakdown.py --target-root <平台的 Skills 根目录> --replace
```

旧版本会先改名为带时间戳的备份目录，不会直接删除。

## 平台兼容原则

- 支持读取 Agent Skills 风格 `SKILL.md` 的平台，可以直接安装整个文件夹。
- 不支持自动发现 Skill 的平台，可以把 `SKILL.md` 作为系统工作流载入，并保持 `references/` 的相对路径可读。
- RenderDoc 接入不限定具体 MCP 工具名；平台只要能调用 RenderDoc MCP、Replay API、qrenderdoc Python Console，或读取预先导出的证据文件即可使用。
- Skill 不包含任何游戏截帧、PPT、PDF、Shader、FBX 或项目交付资源。
