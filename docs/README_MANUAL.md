# Claude Code Skill Registry - 手动安装模式

这是内网私有 Skill Registry，用于在内网环境中分发和安装 Claude Code 技能插件。

## 访问地址

```
http://192.168.56.1:28000
```

## 安装技能的方法

### 方式一：浏览器下载 + 命令行安装

1. **浏览技能**
   - 访问主页：`http://192.168.56.1:28000`
   - 查看可用的技能列表
   - 使用筛选器快速查找

2. **下载 ZIP 文件**
   - 点击版本号链接（如 `v1.0.0`）下载 ZIP 文件
   - 或右键复制链接地址

3. **解压并安装**
   ```bash
   # 创建插件目录
   mkdir -p ~/.claude/plugins/skill-name

   # 解压到插件目录
   unzip skill-name-1.0.0.zip -d ~/.claude/plugins/skill-name/

   # 验证安装
   /plugin list
   ```

### 方式二：命令行直接下载

```bash
# 下载技能包
wget http://192.168.56.1:28000/plugins/collection/skill-name/version.zip

# 或使用 curl
curl -O http://192.168.56.1:28000/plugins/collection/skill-name/version.zip

# 解压安装
unzip version.zip -d ~/.claude/plugins/skill-name/
```

### 方式三：使用 API 获取技能列表

```bash
# 获取 JSON 格式的技能列表
curl http://192.168.56.1:28000/marketplace.json

# 返回示例
{
  "registry": "private-registry",
  "plugin_count": 10,
  "plugins": [
    {
      "name": "my-skill",
      "version": "1.0.0",
      "download_url": "http://192.168.56.1:28000/plugins/default/my-skill/1.0.0.zip",
      "size_kb": 12.5
    }
  ]
}
```

## 目录结构

```
plugins/
├── collection1/
│   ├── skill-a/
│   │   ├── 1.0.0.zip
│   │   └── 2.0.0.zip
│   └── skill-b/
│       └── 1.0.0.zip
└── collection2/
    └── skill-c/
        └── 1.0.0.zip
```

## 上传新技能

管理员可以通过上传页面添加技能：

1. 访问：`http://192.168.56.1:28000/admin/upload`
2. 登录（默认：admin / admin123）
3. 填写信息：
   - **Collection**: 集合名称（如：security、development）
   - **Plugin Name**: 技能名称（如：code-review）
   - **Version**: 版本号（如：1.0.0）
   - **File**: ZIP 文件

4. 点击上传

## 技能 ZIP 文件格式

技能 ZIP 文件应包含以下结构：

```
skill-name-1.0.0.zip
├── .claude-plugin/
│   └── plugin.json    # 技能元数据
├── skills/            # 技能定义文件
│   └── my-skill.md
└── commands/          # 命令脚本（可选）
```

**plugin.json 示例**：
```json
{
  "name": "my-skill",
  "version": "1.0.0",
  "description": "My awesome skill",
  "author": {
    "name": "Your Name"
  }
}
```

## 技能集合上传

可以一次性上传包含多个技能的集合包：

1. 准备 ZIP 文件，结构如下：
   ```
   skills-collection.zip
   └── skills/
       └── plugins/
           ├── skill-a/
           └── skill-b/
   ```

2. 在上传页面，只需填写：
   - **Collection**: 集合名称
   - **File**: 集合 ZIP 文件
   - （不需要填写 Name 和 Version）

系统会自动提取集合中的所有技能。

## API 端点

- `GET /` - 主页（Web UI）
- `GET /marketplace.json` - 技能列表（JSON）
- `GET /api/skills` - 技能列表 API
- `GET /api/collections` - 集合列表
- `GET /plugins/{collection}/{skill}/{version}` - 下载技能
- `POST /admin/upload` - 上传技能（需要登录）
- `DELETE /admin/plugins/{collection}/{skill}/{version}` - 删除技能（需要登录）

## 配置

环境变量：

```bash
# 服务器端口
PORT=28000

# 管理员凭证
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123

# Session 密钥
SECRET_KEY=your-secret-key-change-this

# 插件目录
PLUGINS_DIR=./plugins
```

## Docker 部署

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 常见问题

### Q: 下载后如何验证安装成功？
```bash
/plugin list
```

### Q: 如何更新已安装的技能？
下载新版本 ZIP，解压时覆盖原目录即可。

### Q: 技能安装后不生效？
1. 检查 ZIP 文件结构是否正确
2. 确认 `plugin.json` 存在且格式正确
3. 重启 Claude Code

### Q: 如何批量下载技能？
使用 API 获取列表，然后批量下载：
```bash
# 获取列表
curl http://192.168.56.1:28000/marketplace.json | jq -r '.plugins[].download_url' | xargs -n1 wget
```

## 安全说明

- 默认管理员密码仅用于演示，生产环境请修改
- 建议配置防火墙限制访问
- 敏感技能请使用独立集合并设置访问控制

## 技术支持

如有问题，请联系管理员。
