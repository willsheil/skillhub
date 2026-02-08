# SQLite 到 MySQL 迁移指南

## 环境信息

- Conda 环境：a2a.mysql
- MySQL 服务器：127.0.0.1:3306
- 数据库名：skill
- 用户：root（有完整权限）

## 迁移步骤

### 步骤 1: 激活 Conda 环境并安装 PyMySQL

```bash
# 激活 conda 环境
conda activate a2a.mysql

# 安装 PyMySQL
pip install pymysql
```

### 步骤 2: 确认 MySQL 连接

```bash
# 运行连接检查脚本
python check_mysql.py
```

如果看到 "Connected to MySQL server successfully!" 表示连接正常。

### 步骤 3: 运行数据迁移

```bash
# 运行迁移脚本
python migrate_to_mysql.py
```

迁移脚本会：
- 在 MySQL 中创建所有表（users, skills, downloads）
- 复制 SQLite 中的所有数据到 MySQL
- 验证迁移结果

### 步骤 4: 验证迁移

迁移完成后，脚本会显示：
- Users: SQLite 数量 vs MySQL 数量
- Skills: SQLite 数量 vs MySQL 数量
- Downloads: SQLite 数量 vs MySQL 数量

确认两边数量一致即表示迁移成功。

### 步骤 5: 测试应用

```bash
# 启动服务器
python main.py
```

访问 http://localhost:28000 测试登录功能。

## 常见问题

**Q: 如何回滚到 SQLite？**
A: 备份 database.py 即可回滚。建议在迁移前提交当前代码。

**Q: 可以同时保留 SQLite 和 MySQL 吗？**
A: 可以。数据已迁移到 MySQL 后，SQLite 文件仍然保留在 data/registry.db

**Q: 如何连接到 MySQL 查看数据？**
A:
```bash
mysql -h 127.0.0.1 -P 3306 -u root -p
# 输入密码: root
USE skill;
SHOW TABLES;
```

## 注意事项

1. 确保 MySQL 服务在迁移期间保持运行
2. 迁移过程不会修改 SQLite 数据（安全）
3. 如果迁移失败，可以重新运行迁移脚本（使用 INSERT IGNORE）
