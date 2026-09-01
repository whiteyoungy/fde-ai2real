# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""Lab-10 事件流后台对账智能体。

- `publish.py`：把 fixtures/events.jsonl 灌进 Kafka
- `agent.py`：隔离 → 根因诊断 → 起草补偿（只起草，绝不执行）
"""
