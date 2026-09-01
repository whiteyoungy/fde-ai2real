# 多阶段构建。第 13.1 节讲的那几条在这里都能看到实物：
# builder 阶段的编译工具链不进 runtime，非 root 运行，基础镜像锁死具体 tag。
FROM python:3.12-slim AS builder
WORKDIR /build
# 这个 Lab 的服务只用标准库，没有依赖要装。真实项目里这一层是
# pip install --target=/build/deps -r requirements.txt，产物才需要往下拷。
RUN mkdir -p /build/deps

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /build/deps /app/deps
COPY server.py /app/server.py
ENV PYTHONPATH=/app/deps APP_VERSION=1.0.0 PORT=8080
# 非 root 运行。很多客户的安全基线会强制这一条，写 Dockerfile 时就满足，
# 别等客户扫描工具报错才回头改。
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["python", "-u", "/app/server.py"]
