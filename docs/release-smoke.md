# Release Smoke Test

This smoke test validates the public `v1.0.0` sibling-repo layout:

```text
~/Projects/cortex
~/Projects/cortex-wechat
```

## 1. Validate Compose configuration

```bash
cd ~/Projects/cortex
docker compose config >/dev/null
```

This confirms that the `wechat` service resolves `../cortex-wechat` correctly.

## 2. Start Cortex

Backend-only:

```bash
cd ~/Projects/cortex
docker compose up -d db cortex
```

Full stack:

```bash
cd ~/Projects/cortex
docker compose up -d
```

## 3. Verify API health

```bash
curl -sf http://127.0.0.1:8420/api/v1/health
```

If auth is enabled, source the shared env file before authenticated checks:

```bash
source ~/.cortex/env
```

## 4. Verify authenticated ingest

```bash
curl -sf \
  -H "Authorization: Bearer $CORTEX_API_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST \
  http://127.0.0.1:8420/api/v1/events/ingest \
  -d '{"title":"Smoke Test","content":"release smoke test event","source":"smoke","raw_input_type":"text"}'
```

## 5. Verify `cortex-wechat` foreground startup

```bash
cd ~/Projects/cortex-wechat
bun install
bun run start:ilink
```

Expected result:

- startup logs appear without contract/type errors
- a QR code flow appears if the session is not already authenticated
- after login, the agent stays connected to Cortex at `http://127.0.0.1:8420/api/v1`

## 6. Manual message round-trip

- Send `帮助` or `help` in WeChat
- Confirm the agent responds
- Send a short note or a URL
- Confirm the event appears in the Cortex console or API
