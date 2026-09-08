#!/bin/bash
# 云端全栈回归脚本（在服务器上执行）
set -e
API=http://localhost:9999/api/v1
J() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)"; }

echo "== 1. 健康检查 =="
curl -s --noproxy '*' $API/health; echo

echo "== 2. 注册（已存在则跳过） =="
curl -s --noproxy '*' -X POST $API/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"deploy@agentflow.com","password":"test123456","nickname":"云端部署验证"}' | head -c 200; echo

echo "== 3. 登录 =="
TOKEN=$(curl -s --noproxy '*' -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"deploy@agentflow.com","password":"test123456"}' | J '["access_token"]')
echo "token 长度: ${#TOKEN}"

echo "== 4. 当前订阅 =="
curl -s --noproxy '*' $API/billing/me -H "Authorization: Bearer $TOKEN"; echo

echo "== 5. 提交生成 =="
TASK=$(curl -s --noproxy '*' -X POST $API/generate -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"topic":"云端部署","platform":"xiahs"}' | J '["task_id"]')
echo "task_id: $TASK"

echo "== 6. SSE 前 45 秒事件流 =="
curl -s --noproxy '*' -N --max-time 45 $API/stream/$TASK -H "Authorization: Bearer $TOKEN" | head -c 1500; echo

echo "== 7. 额度扣减核对 =="
curl -s --noproxy '*' $API/billing/me -H "Authorization: Bearer $TOKEN"; echo
echo "REGRESSION_DONE"
