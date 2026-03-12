-- 创建独立测试数据库
-- 运行方式：psql -U postgres -f scripts/create_test_db.sql

-- 如果测试数据库已存在，先删除
DROP DATABASE IF EXISTS jchatmind_test;

-- 创建测试数据库
CREATE DATABASE jchatmind_test
    WITH 
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1;

-- 连接到测试数据库并启用必要的扩展
\c jchatmind_test

-- 启用 UUID 扩展（如果需要）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 启用向量扩展（pgvector，如果使用）
-- CREATE EXTENSION IF NOT EXISTS vector;
