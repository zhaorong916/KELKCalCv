KELKCalCv 服务器部署说明
========================

目录结构
--------
deploy/
  bootstrap.bat       一键首次部署（环境检查/克隆仓库/生成.env/启动）
  update.bat          从 Gitee 拉取最新代码 + 更新依赖
  start-server.bat    启动后端服务（uvicorn + 静态前端）
  stop-server.bat     停止服务（清理 8000 端口）
  部署说明.md          完整部署文档（环境要求/常见问题/安全须知）

首次部署步骤
------------
0. 推荐: 运行 bootstrap.bat 一键完成下述步骤 3~5
1. 在服务器上安装 Python 3.10+ 和 Git
2. 安装 ODBC Driver 17 for SQL Server（pyodbc 连接 SQL Server 必需）
3. 克隆仓库:
     git clone https://gitee.com/KELKzhao/kelkcalcv.git
     cd kelkcalcv
4. 复制 backend/.env.example 为 backend/.env，填入真实数据库密码和 SECRET_KEY
   （.env 已在 .gitignore，不会被 git 覆盖）
5. 运行 deploy\start-server.bat 启动服务
6. 浏览器访问 http://localhost:8000

日常更新
--------
1. 运行 deploy\stop-server.bat 停止服务
2. 运行 deploy\update.bat 拉取最新代码（自动更新依赖）
3. 运行 deploy\start-server.bat 重启服务

配置说明
--------
backend/.env  包含以下关键项（完整列表见 backend/.env.example）:
  DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD   SQL Server 连接
  SECRET_KEY                                             JWT 签名密钥
  BACKEND_CORS_ORIGINS                                   允许的前端源

注意事项
--------
- 批处理文件编码为 UTF-8 with BOM，头部已设 chcp 65001，可正确显示中文
- 服务器本地 backend/.env 不会被 git 覆盖，每次更新安全
- .env.example 中已脱敏为占位符，禁止提交真实密码到仓库
