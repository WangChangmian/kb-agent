# Python 3.12 基础镜像（slim 版：体积小）
FROM docker.m.daocloud.io/python:3.12-slim

WORKDIR /app

# 先只拷依赖文件并安装 → 利用 Docker 层缓存，改代码不用重装依赖
COPY requirements.txt .
RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 再拷全部代码
COPY . .

# 容器内启动 FastAPI：模块路径与本地 `uvicorn app.main:app` 保持一致
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
