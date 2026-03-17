-- Initialize Gitea database
CREATE DATABASE IF NOT EXISTS gitea CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Grant privileges to root for Gitea (already done by default in MySQL 8)
-- The Gitea container will create its own tables on first run
