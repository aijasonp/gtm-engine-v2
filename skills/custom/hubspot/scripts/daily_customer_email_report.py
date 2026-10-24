import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
import re

HUBSPOT_API_ROOT = "https://api.hubapi.com"
SLACK_API_ROOT = "https://slack.com/api"

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Generate a HubSpot Closed Won email digest and send it via Slack DM."
        )
    )
    parser.add_argument(
        "--slack-user",
        required=True,
        help="Slack user ID to DM the summary to",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to look back for email engagements (default: 1)",
    )
    return parser.parse_args()


def get_env_or_exit(key):
    value = os.environ.get(key)
    if not value:
        print(f"Environment variable {key} is required", file=sys.stderr)
        sys.exit(1)
    return value


def http_request(method, url, headers=None, params=None, body=None, max_retries=5):
    if params:
        query = urllib.parse.urlencode(params)
        separator = "&" if urllib.parse.urlsplit(url).query else "?"
        url = f"{url}{separator}{query}"

    payload = None
    if body is not None:
        payload = body if isinstance(body, (bytes, bytearray)) else body.encode("utf-8")

    headers = headers or {}

    attempt = 0
    while True:
        attempt += 1
        req = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                data = response.read()
                if not data:
                    return None
                charset = response.headers.get_content_charset() or "utf-8"
                text = data.decode(charset)
                return json.loads(text)
        except urllib.error.HTTPError as err:
            if err.code in RETRYABLE_STATUS_CODES and attempt < max_retries:
                backoff = 2 ** (attempt - 1)
                time.sleep(backoff)
                continue
            try:
                error_body = err.read().decode("utf-8")
            except Exception:  # pylint: disable=broad-except
                error_body = ""
            raise RuntimeError(
                f"HTTP {err.code} for {url}: {error_body or err.reason}"
            ) from err
        except urllib.error.URLError as err:
            if attempt >= max_retries:
                raise RuntimeError(f"Network error for {url}: {err.reason}") from err
            backoff = 2 ** (attempt - 1)
            time.sleep(backoff)


def fetch_closed_won_deals(token):
    deals = []
    after = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    while True:
        body = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "dealstage",
                            "operator": "EQ",
                            "value": "closedwon",
                        }
                    ]
                }
            ],
            "properties": ["dealname", "closedate"],
            "limit": 100,
        }
        if after is not None:
            body["after"] = after

        response = http_request(
            "POST",
            f"{HUBSPOT_API_ROOT}/crm/v3/objects/deals/search",
            headers=headers,
            body=json.dumps(body),
        )

        if not response:
            break

        deals.extend(response.get("results", []))
        paging = response.get("paging", {})
        next_page = paging.get("next", {})
        after = next_page.get("after")
        if after is None:
            break
    return deals


def fetch_deal_contacts(token, deal_id):
    contacts = []
    after = None
    headers = {"Authorization": f"Bearer {token}"}
    while True:
        params = {"limit": 100}
        if after is not None:
            params["after"] = after
        url = f"{HUBSPOT_API_ROOT}/crm/v3/objects/deals/{deal_id}/associations/contacts"
        response = http_request("GET", url, headers=headers, params=params)
        if not response:
            break

        for association in response.get("results", []):
            contact_id = association.get("id")
            if contact_id:
                contact = fetch_contact_details(token, contact_id)
                if contact:
                    contacts.append(contact)

        paging = response.get("paging", {})
        next_page = paging.get("next", {})
        after = next_page.get("after")
        if after is None:
            break
    return contacts


def fetch_contact_details(token, contact_id):
    headers = {"Authorization": f"Bearer {token}"}
    params = {"properties": "email,firstname,lastname"}
    url = f"{HUBSPOT_API_ROOT}/crm/v3/objects/contacts/{contact_id}"
    response = http_request("GET", url, headers=headers, params=params)
    if not response:
        return None
    properties = response.get("properties", {})
    email = properties.get("email")
    firstname = properties.get("firstname", "")
    lastname = properties.get("lastname", "")
    full_name = " ".join(part for part in [firstname, lastname] if part).strip()
    return {
        "id": contact_id,
        "name": full_name or None,
        "email": email,
    }


def fetch_email_engagements(token, deal_id):
    engagements = []
    offset = 0
    headers = {"Authorization": f"Bearer {token}"}
    while True:
        params = {"limit": 100}
        if offset:
            params["offset"] = offset
        url = (
            f"{HUBSPOT_API_ROOT}/engagements/v1/engagements/associated/deal/{deal_id}/paged"
        )
        response = http_request("GET", url, headers=headers, params=params)
        if not response:
            break
        engagements.extend(response.get("results", []))
        if not response.get("hasMore"):
            break
        offset = response.get("offset")
        if offset is None:
            break
    return engagements


def within_time_window(engagement, threshold):
    engagement_data = engagement.get("engagement", {})
    created = engagement_data.get("createdAt")
    updated = engagement_data.get("lastUpdated")
    timestamps = []
    for value in (created, updated):
        if value is None:
            continue
        try:
            timestamps.append(datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc))
        except (TypeError, ValueError):
            continue
    if not timestamps:
        return False
    latest_time = max(timestamps)
    return latest_time >= threshold, latest_time


def clean_html(text):
    return re.sub(r"<[^>]+>", "", text)


def extract_snippet(metadata):
    text = metadata.get("text")
    if text:
        snippet_source = text
    else:
        html_content = metadata.get("html")
        snippet_source = clean_html(html_content) if html_content else ""
    snippet = snippet_source.strip().replace("\n", " ")
    return snippet[:200]


def format_contacts(contacts):
    if not contacts:
        return "None listed"
    formatted = []
    for contact in contacts:
        name = contact.get("name")
        email = contact.get("email")
        if name and email:
            formatted.append(f"{name} <{email}>")
        elif email:
            formatted.append(email)
        elif name:
            formatted.append(name)
    return ", ".join(formatted) if formatted else "None listed"


def build_summary(deal_name, closedate, contacts, entries):
    lines = []
    lines.append(f"Deal: {deal_name}")
    if closedate:
        try:
            closed_ts = datetime.fromtimestamp(int(closedate) / 1000, tz=timezone.utc)
            lines.append(f"Closed: {closed_ts.strftime('%Y-%m-%d')}")
        except (TypeError, ValueError):
            lines.append(f"Closed: {closedate}")
    lines.append(f"Contacts: {format_contacts(contacts)}")
    lines.append("Emails:")
    for entry in entries:
        lines.append(
            f"  - [{entry['timestamp']}] {entry['subject'] or 'No subject'}"
        )
        lines.append(
            f"    From: {entry['sender'] or 'Unknown'} | To: {entry['recipients'] or 'Unknown'}"
        )
        if entry['snippet']:
            lines.append(f"    Snippet: {entry['snippet']}")
    return "\n".join(lines)


def send_slack_message(token, user_id, message):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    body = json.dumps({"channel": user_id, "text": message})
    response = http_request(
        "POST", f"{SLACK_API_ROOT}/chat.postMessage", headers=headers, body=body
    )
    if not response or not response.get("ok"):
        raise RuntimeError(f"Slack API error: {response}")


def main():
    args = parse_args()
    hubspot_token = get_env_or_exit("HUBSPOT_API_TOKEN")
    slack_token = get_env_or_exit("SLACK_BOT_TOKEN")

    threshold = datetime.now(timezone.utc) - timedelta(days=args.days)

    deals = fetch_closed_won_deals(hubspot_token)

    digest_sections = []
    email_count = 0

    for deal in deals:
        deal_id = deal.get("id")
        properties = deal.get("properties", {})
        deal_name = properties.get("dealname") or f"Deal {deal_id}"
        closedate = properties.get("closedate")

        contacts = fetch_deal_contacts(hubspot_token, deal_id)
        engagements = fetch_email_engagements(hubspot_token, deal_id)

        relevant_entries = []
        for engagement in engagements:
            engagement_info = engagement.get("engagement", {})
            if engagement_info.get("type") != "EMAIL":
                continue
            in_window, latest_time = within_time_window(engagement, threshold)
            if not in_window:
                continue
            metadata = engagement.get("metadata", {})
            recipients = ", ".join(
                [rcpt.get("email") for rcpt in metadata.get("to", []) if rcpt.get("email")]
            )
            entry = {
                "subject": metadata.get("subject"),
                "sender": metadata.get("from", {}).get("email"),
                "recipients": recipients or None,
                "timestamp": latest_time.strftime("%Y-%m-%d %H:%M UTC") if latest_time else "",
                "snippet": extract_snippet(metadata),
            }
            relevant_entries.append(entry)

        if relevant_entries:
            email_count += len(relevant_entries)
            digest_sections.append(
                build_summary(deal_name, closedate, contacts, relevant_entries)
            )

    if not digest_sections:
        message = f"No customer emails logged in HubSpot in the last {args.days} day(s)."
    else:
        header = (
            f"HubSpot Closed Won Email Digest (last {args.days} day(s))\n"
            f"Total emails: {email_count}\n"
            "\n"
        )
        message = header + "\n\n".join(digest_sections)

    print(message)
    send_slack_message(slack_token, args.slack_user, message)


if __name__ == "__main__":
    main()
