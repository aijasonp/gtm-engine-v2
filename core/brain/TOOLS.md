# TOOLS.md - Integration Quick Reference
Full detail: references/tools-detail.md

## Key Integrations
- **{{COMPANY}} API**: COMPANY_API_KEY in .env. Base: https://llm.example.com/v1/
- **HubSpot**: HUBSPOT_TOKEN + HUBSPOT_API_TOKEN in .env. Write access enabled.
- **Lemlist**: LEMLIST_API_KEY. Basic auth. Team tea_REDACTED.
- **Smartlead**: SMARTLEAD_API_KEY. 5 domains: companyai.co/example.com/usecompany.com/companyplatform.com/companyharness.com
- **Clay**: Use ~/.local/bin/clay-bin. Workspace 0000000. DEFAULT enrichment provider.
- **Google Workspace**: Use gwsg (not gws). Credentials at ~/.config/gws/
- **GitHub App**: gtm-agent-app (ID 0000000). refresh-gh-auth.sh for token refresh.
- **Linear**: LINEAR_API_KEY in .env. linear-refresh.sh auto-refreshes every 20h.
- **Aircall**: AIRCALL_API_ID + AIRCALL_API_TOKEN in .env.
- **Notion**: API key at ~/.config/notion/api_key
- **Cloudflare Clef**: CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_AUTH_TOKEN in .env. Replaced Jev.
- **Zoom**: ZOOM_CLIENT_ID/SECRET/REFRESH_TOKEN in .env.
- **Granola**: GRANOLA_API_KEY in .env. Jason Polanco personal key.
- **Retrieval**: https://internal-host.example.ts.net. Token at ~/.config/retrieval-service/token
- **company-skills**: Skills on-demand at ~/.openclaw/workspace/company-skills/<skill>/SKILL.md
