#!/bin/bash

cd /home/erictsou/tender-tracker

# 先停止舊的 vLLM 進程
pkill -9 -f "vllm serve" 2>/dev/null
pkill -9 -f "VLLM::EngineCore" 2>/dev/null
sleep 2

# 禁用 Flash Attention，使用 eager mode
export VLLM_ATTENTION_BACKEND=XFORMERS

# 使用 nohup 在背景執行
nohup uv run vllm serve Qwen/Qwen3-8B \
    --port 8765 \
    --max-model-len 4096 \
    --enforce-eager \
    --dtype float16 \
    --gpu-memory-utilization 0.85 \
    > /home/erictsou/tender-tracker/logs/vllm.log 2>&1 &

echo "vLLM 已在背景啟動，PID: $!"
echo "查看 log: tail -f ~/tender-tracker/logs/vllm.log"
