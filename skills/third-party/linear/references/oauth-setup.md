# Linear OAuth Setup for Agent Identity

This guide sets up a dedicated Linear identity for an OpenClaw agent (so actions appear as the agent, not a human).

## 1. Create OAuth Application

Go to https://linear.app/settings/api/applications → Create Application

- **Name:** Your agent name (e.g., "{{OPS_AGENT}}")
- **Redirect URI:** A URL your agent's host can serve and that the authorizing human can reach in their browser
  - Same machine: `http://localhost:3456/callback`
  - Remote host: Use a Tailscale URL like `https://your-host.tail.ts.net:3456/callback`
- **Scopes:** `read`, `write`, `issues:create`, `comments:create`

Save the **Client ID** and **Client Secret**.

## 2. Authorization Flow

Your agent needs to:

1. Start a temporary HTTP server on the callback port
2. Generate the authorization URL:
   ```
   https://linear.app/oauth/authorize?client_id=CLIENT_ID&redirect_uri=REDIRECT_URI&response_type=code&scope=read,write,issues:create,comments:create&state=RANDOM_STATE
   ```
3. Present the URL to the human operator to click
4. Human authorizes in their browser → redirected to callback with `?code=AUTH_CODE`
5. Exchange the code for tokens:
   ```bash
   curl -s -X POST https://api.linear.app/oauth/token \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=authorization_code&code=AUTH_CODE&redirect_uri=REDIRECT_URI&client_id=CLIENT_ID&client_secret=CLIENT_SECRET"
   ```
6. Save the `access_token` and `refresh_token`

## 3. Token Refresh

Linear OAuth tokens expire after ~24 hours. Set up automated refresh:

```bash
curl -s -X POST https://api.linear.app/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=refresh_token&refresh_token=REFRESH_TOKEN&client_id=CLIENT_ID&client_secret=CLIENT_SECRET"
```

Run this on a schedule (e.g., every 20 hours via cron or LaunchAgent) and update `LINEAR_API_KEY` with the new access token.

## 4. Agent Identity

After OAuth setup, run the viewer query to confirm your agent identity:

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ viewer { id name email } }"}' | jq .
```

The agent will appear as an "App" actor in Linear, with its own identity separate from any human user.
