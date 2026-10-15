# 医院信息系统实验一

运行前将 .env.example 复制为 .env，在本机填写数据库密码；.env 不上传。
中文目录下显式指定英文项目名。已有部署请沿用原项目名与原密码。

```powershell
Copy-Item .env.example .env
# 编辑 .env 后，检查配置
docker compose --project-name openmrs-lab config --quiet
# 按实验需要自行启动
docker compose --project-name openmrs-lab up -d
```

教学 PDF 中显示的密码已移除；部署参数以本地 .env 为准。
