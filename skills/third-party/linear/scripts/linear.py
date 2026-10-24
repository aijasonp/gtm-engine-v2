#!/usr/bin/env python3
"""
Linear API client — stdlib only (urllib, json).
Covers common operations via Linear's GraphQL API.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.linear.app/graphql"


def load_api_key():
    """Read Linear API key from OpenClaw config or env var."""
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    try:
        with open(config_path) as f:
            config = json.load(f)
        return config["skills"]["entries"]["linear"]["apiKey"]
    except (FileNotFoundError, KeyError, TypeError):
        pass
    key = os.environ.get("LINEAR_API_KEY")
    if key:
        return key
    print(
        "Error: No Linear API key. Set skills.entries.linear.apiKey in openclaw.json "
        "or LINEAR_API_KEY env var.",
        file=sys.stderr,
    )
    sys.exit(1)


def graphql(query, variables=None, _retries=3, partial=False):
    """Execute a GraphQL query against the Linear API with retry on 429.

    If partial=True, return whatever data is available even when GraphQL errors
    are present (useful for alias-based batch queries where some items may not exist).
    """
    api_key = load_api_key()
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Authorization": api_key, "Content-Type": "application/json"},
    )
    for attempt in range(_retries):
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < _retries - 1:
                wait = int(e.headers.get("Retry-After", 2 ** attempt))
                print(f"Rate limited, retrying in {wait}s...", file=sys.stderr)
                import time
                time.sleep(wait)
                continue
            body = e.read().decode()
            print(f"HTTP {e.code}: {body}", file=sys.stderr)
            sys.exit(1)
        if "errors" in data:
            if partial:
                # In partial mode, return whatever data is available (may be None)
                for err in data["errors"]:
                    path = ".".join(str(p) for p in err.get("path", []))
                    print(f"Warning: {err['message']} (path: {path})", file=sys.stderr)
                return data.get("data")  # may be None if entire query errored
            print(
                f"GraphQL errors: {json.dumps(data['errors'], indent=2)}",
                file=sys.stderr,
            )
            sys.exit(1)
        return data["data"]


def out(data, pretty=False):
    """Print JSON output."""
    print(json.dumps(data, indent=2) if pretty else json.dumps(data))


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def cmd_me(args):
    """Get authenticated user info."""
    data = graphql("query { viewer { id name email displayName admin active } }")
    out(data["viewer"], args.pretty)


def cmd_teams(args):
    """List all teams."""
    data = graphql(
        "query { teams { nodes { id name key description } } }"
    )
    out(data["teams"]["nodes"], args.pretty)


def cmd_states(args):
    """List workflow states, optionally filtered by team key."""
    data = graphql(
        """
        query {
            workflowStates(first: 200) {
                nodes { id name type position team { key name } }
            }
        }
        """
    )
    nodes = data["workflowStates"]["nodes"]
    if args.team:
        nodes = [n for n in nodes if n["team"]["key"] == args.team.upper()]
    # Sort by team key, then position
    nodes.sort(key=lambda n: (n["team"]["key"], n["position"]))
    out(nodes, args.pretty)


def cmd_labels(args):
    """List all issue labels."""
    data = graphql(
        """
        query {
            issueLabels(first: 200) {
                nodes { id name color parent { name } }
            }
        }
        """
    )
    out(data["issueLabels"]["nodes"], args.pretty)


def cmd_cycles(args):
    """List cycles, optionally filtered by team key."""
    filter_obj = {}
    if args.team:
        filter_obj["team"] = {"key": {"eq": args.team.upper()}}
    data = graphql(
        """
        query($filter: CycleFilter, $first: Int) {
            cycles(filter: $filter, first: $first, orderBy: createdAt) {
                nodes {
                    id name number startsAt endsAt
                    progress completedScopeCount scopeCount
                    team { key name }
                }
            }
        }
        """,
        {"filter": filter_obj or None, "first": args.limit},
    )
    out(data["cycles"]["nodes"], args.pretty)


def cmd_projects(args):
    """List projects."""
    data = graphql(
        """
        query($first: Int) {
            projects(first: $first) {
                nodes {
                    id name state slugId progress
                    startDate targetDate
                    lead { name }
                    teams { nodes { key } }
                }
            }
        }
        """,
        {"first": args.limit},
    )
    out(data["projects"]["nodes"], args.pretty)


def cmd_issue(args):
    """Get detailed info for a single issue by identifier (e.g. ENG-123)."""
    data = graphql(
        """
        query($id: String!) {
            issue(id: $id) {
                id identifier title description priority priorityLabel
                url estimate
                state { id name type }
                assignee { id name }
                labels { nodes { name } }
                team { key name }
                cycle { id name number }
                project { id name }
                parent { id identifier title }
                children { nodes { id identifier title state { name } } }
                createdAt updatedAt completedAt
                comments { nodes { body createdAt user { name } } }
            }
        }
        """,
        {"id": args.identifier},
    )
    out(data["issue"], args.pretty)


def cmd_issues(args):
    """List/filter issues."""
    filter_obj = {}
    if args.team:
        filter_obj["team"] = {"key": {"eq": args.team.upper()}}
    if args.state:
        filter_obj["state"] = {"name": {"in": args.state}}
    if args.assignee:
        filter_obj["assignee"] = {"name": {"containsIgnoreCase": args.assignee}}
    if args.label:
        filter_obj["labels"] = {"name": {"in": args.label}}
    if args.priority is not None:
        filter_obj["priority"] = {"lte": args.priority}
    if args.project:
        filter_obj["project"] = {"name": {"containsIgnoreCase": args.project}}
    if args.cycle:
        filter_obj["cycle"] = {"name": {"containsIgnoreCase": args.cycle}}

    data = graphql(
        """
        query($filter: IssueFilter, $first: Int, $after: String) {
            issues(filter: $filter, first: $first, after: $after) {
                nodes {
                    id identifier title priority priorityLabel
                    state { name type }
                    assignee { name }
                    labels { nodes { name } }
                    team { key }
                    cycle { name number }
                    project { name }
                    estimate
                    createdAt updatedAt
                }
                pageInfo { hasNextPage endCursor }
            }
        }
        """,
        {
            "filter": filter_obj or None,
            "first": args.limit,
            "after": args.after,
        },
    )
    out(data["issues"], args.pretty)


def _is_uuid(s):
    """Check if a string looks like a UUID."""
    return len(s) == 36 and s.count("-") == 4


def _resolve_customer_id(name_or_id):
    """Resolve a customer name to its UUID. Returns as-is if already a UUID."""
    if _is_uuid(name_or_id):
        return name_or_id
    data = graphql(
        """
        query($filter: CustomerFilter) {
            customers(filter: $filter, first: 1) {
                nodes { id name }
            }
        }
        """,
        {"filter": {"name": {"eqIgnoreCase": name_or_id}}},
    )
    nodes = data["customers"]["nodes"]
    if not nodes:
        print(f"Error: Customer '{name_or_id}' not found.", file=sys.stderr)
        sys.exit(1)
    return nodes[0]["id"]


def _resolve_customer_status_id(name_or_id):
    """Resolve a customer status name/displayName to its UUID."""
    if _is_uuid(name_or_id):
        return name_or_id
    data = graphql(
        """
        query {
            customerStatuses(first: 250) {
                nodes { id name displayName }
            }
        }
        """
    )
    lower = name_or_id.lower()
    for s in data["customerStatuses"]["nodes"]:
        if s.get("name", "").lower() == lower or s.get("displayName", "").lower() == lower:
            return s["id"]
    print(f"Error: Customer status '{name_or_id}' not found.", file=sys.stderr)
    sys.exit(1)


def _resolve_customer_tier_id(name_or_id):
    """Resolve a customer tier name/displayName to its UUID."""
    if _is_uuid(name_or_id):
        return name_or_id
    data = graphql(
        """
        query {
            customerTiers(first: 250) {
                nodes { id name displayName }
            }
        }
        """
    )
    lower = name_or_id.lower()
    for t in data["customerTiers"]["nodes"]:
        if t.get("name", "").lower() == lower or t.get("displayName", "").lower() == lower:
            return t["id"]
    print(f"Error: Customer tier '{name_or_id}' not found.", file=sys.stderr)
    sys.exit(1)


def _resolve_user_id(name_or_id):
    """Resolve a user name/email/displayName to UUID."""
    if _is_uuid(name_or_id):
        return name_or_id
    data = graphql(
        """
        query {
            users(first: 200) {
                nodes { id name email displayName }
            }
        }
        """
    )
    lower = name_or_id.lower()
    for u in data["users"]["nodes"]:
        if (
            u.get("email", "").lower() == lower
            or u.get("name", "").lower() == lower
            or u.get("displayName", "").lower() == lower
        ):
            return u["id"]
    print(f"Error: User '{name_or_id}' not found.", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Customer queries
# ---------------------------------------------------------------------------

CUSTOMERS_QUERY = """
query Customers($filter: CustomerFilter, $first: Int, $after: String, $before: String, $includeArchived: Boolean, $orderBy: PaginationOrderBy) {
  customers(filter: $filter, first: $first, after: $after, before: $before, includeArchived: $includeArchived, orderBy: $orderBy) {
    nodes {
      id name domains externalIds slackChannelId revenue size
      approximateNeedCount slugId url
      owner { id name displayName email }
      status { id name displayName color description }
      tier { id name displayName color description }
      createdAt updatedAt archivedAt
    }
    pageInfo { hasNextPage hasPreviousPage startCursor endCursor }
  }
}
"""

CUSTOMER_QUERY = """
query Customer($id: String!) {
  customer(id: $id) {
    id name domains externalIds slackChannelId revenue size
    approximateNeedCount slugId url logoUrl mainSourceId
    owner { id name displayName email }
    status { id name displayName color description }
    tier { id name displayName color description }
    createdAt updatedAt archivedAt
  }
}
"""

CUSTOMER_NEEDS_QUERY = """
query CustomerNeeds($filter: CustomerNeedFilter, $first: Int, $after: String, $before: String, $includeArchived: Boolean, $orderBy: PaginationOrderBy) {
  customerNeeds(filter: $filter, first: $first, after: $after, before: $before, includeArchived: $includeArchived, orderBy: $orderBy) {
    nodes {
      id priority body bodyData url
      customer { id name }
      issue { id identifier title }
      project { id name }
      comment { id }
      creator { id name displayName }
      createdAt updatedAt archivedAt
    }
    pageInfo { hasNextPage hasPreviousPage startCursor endCursor }
  }
}
"""

CUSTOMER_NEED_QUERY = """
query CustomerNeed($id: String!) {
  customerNeed(id: $id) {
    id priority body bodyData url
    customer { id name }
    issue { id identifier title }
    project { id name }
    comment { id }
    creator { id name displayName }
    createdAt updatedAt archivedAt
  }
}
"""

CREATE_CUSTOMER_MUTATION = """
mutation CreateCustomer($input: CustomerCreateInput!) {
  customerCreate(input: $input) {
    success
    customer {
      id name url domains externalIds slackChannelId revenue size
      owner { id name displayName email }
      status { id name displayName }
      tier { id name displayName }
    }
  }
}
"""

UPDATE_CUSTOMER_MUTATION = """
mutation UpdateCustomer($id: String!, $input: CustomerUpdateInput!) {
  customerUpdate(id: $id, input: $input) {
    success
    customer {
      id name url domains externalIds slackChannelId revenue size
      owner { id name displayName email }
      status { id name displayName }
      tier { id name displayName }
    }
  }
}
"""


def cmd_customers(args):
    """List customers with filtering."""
    filter_obj = {}
    if args.name:
        filter_obj["name"] = {"containsIgnoreCase": args.name}
    if args.tier:
        if _is_uuid(args.tier):
            filter_obj["tier"] = {"id": {"eq": args.tier}}
        else:
            filter_obj["tier"] = {"name": {"eqIgnoreCase": args.tier}}
    if args.status:
        if _is_uuid(args.status):
            filter_obj["status"] = {"id": {"eq": args.status}}
        else:
            filter_obj["status"] = {"name": {"eqIgnoreCase": args.status}}

    variables = {"first": args.limit, "includeArchived": args.include_archived}
    if filter_obj:
        variables["filter"] = filter_obj
    if args.after:
        variables["after"] = args.after

    data = graphql(CUSTOMERS_QUERY, variables)
    out(data["customers"], args.pretty)


def cmd_customer(args):
    """Get a single customer by UUID or name."""
    if _is_uuid(args.customer):
        data = graphql(CUSTOMER_QUERY, {"id": args.customer})
        if not data.get("customer"):
            print(f"Error: Customer '{args.customer}' not found.", file=sys.stderr)
            sys.exit(1)
        out(data["customer"], args.pretty)
    else:
        data = graphql(
            CUSTOMERS_QUERY,
            {"filter": {"name": {"eqIgnoreCase": args.customer}}, "first": 1},
        )
        nodes = data["customers"]["nodes"]
        if not nodes:
            print(f"Error: Customer '{args.customer}' not found.", file=sys.stderr)
            sys.exit(1)
        out(nodes[0], args.pretty)


def cmd_customer_requests(args):
    """List customer requests (needs) with filtering."""
    filter_obj = {}
    if args.customer:
        if _is_uuid(args.customer):
            filter_obj["customer"] = {"id": {"eq": args.customer}}
        else:
            filter_obj["customer"] = {"name": {"eqIgnoreCase": args.customer}}
    if args.priority is not None:
        filter_obj["priority"] = {"eq": args.priority}
    if args.issue_id:
        filter_obj["issue"] = {"id": {"eq": args.issue_id}}

    variables = {"first": args.limit, "includeArchived": args.include_archived}
    if filter_obj:
        variables["filter"] = filter_obj
    if args.after:
        variables["after"] = args.after

    data = graphql(CUSTOMER_NEEDS_QUERY, variables)
    out(data["customerNeeds"], args.pretty)


def cmd_customer_request(args):
    """Get a single customer request by UUID."""
    data = graphql(CUSTOMER_NEED_QUERY, {"id": args.id})
    if not data.get("customerNeed"):
        print(f"Error: Customer request '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)
    out(data["customerNeed"], args.pretty)


def cmd_customer_statuses(args):
    """List customer statuses."""
    data = graphql(
        """
        query($first: Int, $includeArchived: Boolean) {
            customerStatuses(first: $first, includeArchived: $includeArchived) {
                nodes {
                    id name displayName color description position
                    createdAt updatedAt archivedAt
                }
            }
        }
        """,
        {"first": 250, "includeArchived": args.include_archived},
    )
    out(data["customerStatuses"]["nodes"], args.pretty)


def cmd_customer_tiers(args):
    """List customer tiers."""
    data = graphql(
        """
        query($first: Int, $includeArchived: Boolean) {
            customerTiers(first: $first, includeArchived: $includeArchived) {
                nodes {
                    id name displayName color description position
                    createdAt updatedAt archivedAt
                }
            }
        }
        """,
        {"first": 250, "includeArchived": args.include_archived},
    )
    out(data["customerTiers"]["nodes"], args.pretty)


def cmd_create_customer(args):
    """Create a customer."""
    inp = {"name": args.name}
    if args.domains:
        inp["domains"] = args.domains
    if args.external_ids:
        inp["externalIds"] = args.external_ids
    if args.slack_channel_id:
        inp["slackChannelId"] = args.slack_channel_id
    if args.revenue is not None:
        inp["revenue"] = args.revenue
    if args.size is not None:
        inp["size"] = args.size
    if args.owner:
        inp["ownerId"] = _resolve_user_id(args.owner)
    if args.status:
        inp["statusId"] = _resolve_customer_status_id(args.status)
    if args.tier:
        inp["tierId"] = _resolve_customer_tier_id(args.tier)

    data = graphql(CREATE_CUSTOMER_MUTATION, {"input": inp})
    result = data["customerCreate"]
    if not result.get("success"):
        print("Error: Failed to create customer.", file=sys.stderr)
        sys.exit(1)
    out(result, args.pretty)


def cmd_update_customer(args):
    """Update an existing customer."""
    customer_id = _resolve_customer_id(args.customer)
    inp = {}
    if args.name:
        inp["name"] = args.name
    if args.domains is not None:
        inp["domains"] = args.domains
    if args.external_ids is not None:
        inp["externalIds"] = args.external_ids
    if args.slack_channel_id is not None:
        inp["slackChannelId"] = args.slack_channel_id or None
    if args.revenue is not None:
        inp["revenue"] = args.revenue
    if args.size is not None:
        inp["size"] = args.size
    if args.owner is not None:
        inp["ownerId"] = _resolve_user_id(args.owner) if args.owner else None
    if args.status is not None:
        inp["statusId"] = _resolve_customer_status_id(args.status) if args.status else None
    if args.tier is not None:
        inp["tierId"] = _resolve_customer_tier_id(args.tier) if args.tier else None

    if not inp:
        print("Error: provide at least one field to update.", file=sys.stderr)
        sys.exit(1)

    data = graphql(UPDATE_CUSTOMER_MUTATION, {"id": customer_id, "input": inp})
    result = data["customerUpdate"]
    if not result.get("success"):
        print("Error: Failed to update customer.", file=sys.stderr)
        sys.exit(1)
    out(result, args.pretty)


def cmd_search(args):
    """Search issues by title/description text."""
    data = graphql(
        """
        query($filter: IssueFilter, $first: Int) {
            issues(filter: $filter, first: $first) {
                nodes {
                    id identifier title priority priorityLabel
                    state { name type }
                    assignee { name }
                    team { key }
                    url
                }
            }
        }
        """,
        {
            "filter": {
                "or": [
                    {"title": {"containsIgnoreCase": args.query}},
                    {"description": {"containsIgnoreCase": args.query}},
                ]
            },
            "first": args.limit,
        },
    )
    out(data["issues"]["nodes"], args.pretty)


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


def cmd_create_issue(args):
    """Create a new issue."""
    inp = {"teamId": args.team_id, "title": args.title}
    if args.description:
        inp["description"] = args.description
    if args.assignee_id:
        inp["assigneeId"] = args.assignee_id
    if args.state_id:
        inp["stateId"] = args.state_id
    if args.label_ids:
        inp["labelIds"] = args.label_ids
    if args.priority is not None:
        inp["priority"] = args.priority
    if args.project_id:
        inp["projectId"] = args.project_id
    if args.cycle_id:
        inp["cycleId"] = args.cycle_id
    if args.estimate is not None:
        inp["estimate"] = args.estimate
    if args.parent_id:
        inp["parentId"] = args.parent_id

    data = graphql(
        """
        mutation($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id identifier title url
                    state { name }
                    assignee { name }
                    team { key }
                }
            }
        }
        """,
        {"input": inp},
    )
    out(data["issueCreate"], args.pretty)


def cmd_update_issue(args):
    """Update an existing issue."""
    inp = {}
    if args.title:
        inp["title"] = args.title
    if args.description:
        inp["description"] = args.description
    if args.state_id:
        inp["stateId"] = args.state_id
    if args.assignee_id:
        inp["assigneeId"] = args.assignee_id
    if args.priority is not None:
        inp["priority"] = args.priority
    if args.label_ids:
        inp["labelIds"] = args.label_ids
    if args.project_id:
        inp["projectId"] = args.project_id
    if args.cycle_id:
        inp["cycleId"] = args.cycle_id
    if args.estimate is not None:
        inp["estimate"] = args.estimate
    if args.parent_id:
        inp["parentId"] = args.parent_id

    if not inp:
        print("Error: provide at least one field to update.", file=sys.stderr)
        sys.exit(1)

    data = graphql(
        """
        mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue {
                    id identifier title url
                    state { name }
                    assignee { name }
                }
            }
        }
        """,
        {"id": args.identifier, "input": inp},
    )
    out(data["issueUpdate"], args.pretty)


def cmd_archive_issue(args):
    """Archive an issue."""
    data = graphql(
        """
        mutation($id: String!) {
            issueArchive(id: $id) { success }
        }
        """,
        {"id": args.identifier},
    )
    out(data["issueArchive"], args.pretty)


def cmd_comment(args):
    """Add a comment to an issue."""
    data = graphql(
        """
        mutation($input: CommentCreateInput!) {
            commentCreate(input: $input) {
                success
                comment { id body createdAt user { name } }
            }
        }
        """,
        {"input": {"issueId": args.issue_id, "body": args.body}},
    )
    out(data["commentCreate"], args.pretty)


def cmd_users(args):
    """List all users in the workspace."""
    data = graphql(
        """
        query {
            users(first: 200) {
                nodes { id name email displayName active admin }
            }
        }
        """
    )
    out(data["users"]["nodes"], args.pretty)


def cmd_create_relation(args):
    """Create a relation between two issues."""
    data = graphql(
        """
        mutation($input: IssueRelationCreateInput!) {
            issueRelationCreate(input: $input) {
                success
                issueRelation { id type }
            }
        }
        """,
        {
            "input": {
                "issueId": args.issue_id,
                "relatedIssueId": args.related_issue_id,
                "type": args.type,
            }
        },
    )
    out(data["issueRelationCreate"], args.pretty)


def cmd_create_project(args):
    """Create a new project."""
    inp = {"name": args.name, "teamIds": args.team_ids}
    if args.description:
        inp["description"] = args.description
    if args.lead_id:
        inp["leadId"] = args.lead_id
    if args.start_date:
        inp["startDate"] = args.start_date
    if args.target_date:
        inp["targetDate"] = args.target_date

    data = graphql(
        """
        mutation($input: ProjectCreateInput!) {
            projectCreate(input: $input) {
                success
                project { id name url }
            }
        }
        """,
        {"input": inp},
    )
    out(data["projectCreate"], args.pretty)


def _resolve_project_id(name_or_id):
    """Resolve a project name (partial match) or UUID to a project ID."""
    # If it looks like a UUID, use it directly
    if len(name_or_id) == 36 and name_or_id.count("-") == 4:
        return name_or_id
    # Otherwise search by name
    data = graphql(
        """
        query($first: Int) {
            projects(first: $first) {
                nodes { id name }
            }
        }
        """,
        {"first": 100},
    )
    for p in data["projects"]["nodes"]:
        if name_or_id.lower() in p["name"].lower():
            return p["id"]
    print(f"Error: No project found matching '{name_or_id}'", file=sys.stderr)
    sys.exit(1)


def cmd_project_updates(args):
    """List project updates."""
    project_id = _resolve_project_id(args.project)
    order = "createdAt" if args.order_by == "createdAt" else "updatedAt"
    data = graphql(
        """
        query($projectId: String!, $first: Int, $after: String, $orderBy: PaginationOrderBy, $includeArchived: Boolean) {
            project(id: $projectId) {
                projectUpdates(first: $first, after: $after, orderBy: $orderBy, includeArchived: $includeArchived) {
                    nodes {
                        id body health createdAt updatedAt
                        user { name }
                        diffMarkdown
                    }
                    pageInfo { hasNextPage endCursor }
                }
            }
        }
        """,
        {
            "projectId": project_id,
            "first": args.limit,
            "after": args.after,
            "orderBy": order,
            "includeArchived": args.include_archived,
        },
    )
    out(data["project"]["projectUpdates"], args.pretty)


def cmd_project_update(args):
    """Get a single project update by ID."""
    data = graphql(
        """
        query($id: String!) {
            projectUpdate(id: $id) {
                id body health createdAt updatedAt
                user { name }
                project { id name }
                diffMarkdown
            }
        }
        """,
        {"id": args.id},
    )
    out(data["projectUpdate"], args.pretty)


def cmd_create_project_update(args):
    """Create a project update."""
    project_id = _resolve_project_id(args.project)
    inp = {"projectId": project_id, "body": args.body}
    if args.health:
        inp["health"] = args.health
    if args.hide_diff:
        inp["isDiffHidden"] = True

    data = graphql(
        """
        mutation($input: ProjectUpdateCreateInput!) {
            projectUpdateCreate(input: $input) {
                success
                projectUpdate { id body health createdAt user { name } project { name } }
            }
        }
        """,
        {"input": inp},
    )
    out(data["projectUpdateCreate"], args.pretty)


def cmd_update_project_update(args):
    """Update an existing project update."""
    inp = {}
    if args.body:
        inp["body"] = args.body
    if args.health:
        inp["health"] = args.health
    if args.hide_diff is not None:
        inp["isDiffHidden"] = args.hide_diff

    if not inp:
        print("Error: provide at least one field to update.", file=sys.stderr)
        sys.exit(1)

    data = graphql(
        """
        mutation($id: String!, $input: ProjectUpdateUpdateInput!) {
            projectUpdateUpdate(id: $id, input: $input) {
                success
                projectUpdate { id body health updatedAt }
            }
        }
        """,
        {"id": args.id, "input": inp},
    )
    out(data["projectUpdateUpdate"], args.pretty)


def cmd_delete_project_update(args):
    """Delete a project update."""
    data = graphql(
        """
        mutation($id: String!) {
            projectUpdateDelete(id: $id) { success }
        }
        """,
        {"id": args.id},
    )
    out(data["projectUpdateDelete"], args.pretty)


def cmd_attach_url(args):
    """Attach a URL to an issue (shows as linked resource in sidebar)."""
    inp = {"issueId": args.issue_id, "url": args.url, "title": args.title}
    if args.subtitle:
        inp["subtitle"] = args.subtitle
    if args.icon_url:
        inp["iconUrl"] = args.icon_url

    data = graphql(
        """
        mutation($input: AttachmentCreateInput!) {
            attachmentCreate(input: $input) {
                success
                attachment { id url title subtitle }
            }
        }
        """,
        {"input": inp},
    )
    out(data["attachmentCreate"], args.pretty)


def cmd_attach_slack(args):
    """Link a Slack message/thread to an issue (Slack-native attachment with optional comment sync)."""
    variables = {"issueId": args.issue_id, "url": args.url}
    if args.title:
        variables["title"] = args.title
    if args.sync:
        variables["syncToCommentThread"] = True

    data = graphql(
        """
        mutation($issueId: String!, $url: String!, $title: String, $syncToCommentThread: Boolean) {
            attachmentLinkSlack(
                issueId: $issueId,
                url: $url,
                title: $title,
                syncToCommentThread: $syncToCommentThread
            ) {
                success
                attachment { id url title }
            }
        }
        """,
        variables,
    )
    out(data["attachmentLinkSlack"], args.pretty)


_BATCH_GET_FIELDS = (
    " id identifier title description priority priorityLabel"
    " url estimate"
    " state { id name type }"
    " assignee { id name }"
    " labels { nodes { name } }"
    " team { key name }"
    " cycle { id name number }"
    " project { id name }"
    " parent { id identifier title }"
    " children { nodes { id identifier title state { name } } }"
    " createdAt updatedAt completedAt"
)


def cmd_batch_get(args):
    """Fetch multiple issues by identifier in batched queries.

    Uses GraphQL aliases for efficiency (10 issues per round trip).
    If a batch fails (e.g. one issue not found — Linear nullifies the
    entire response), falls back to individual queries for that batch
    so valid issues are still returned.
    """
    identifiers = args.identifiers
    all_issues = []
    for i in range(0, len(identifiers), 10):
        batch = identifiers[i : i + 10]
        parts = []
        for j, ident in enumerate(batch):
            parts.append(f'i{j}: issue(id: "{ident}") {{{_BATCH_GET_FIELDS} }}')
        query = "query { " + " ".join(parts) + " }"
        data = graphql(query, partial=True)
        if data is not None:
            # Batch succeeded — collect all results
            for j in range(len(batch)):
                result = data.get(f"i{j}")
                if result is not None:
                    all_issues.append(result)
        else:
            # Batch failed (Linear nullifies data on any alias error) —
            # fall back to individual queries with partial mode
            for ident in batch:
                single = graphql(
                    f"query($id: String!) {{ issue(id: $id) {{{_BATCH_GET_FIELDS} }} }}",
                    {"id": ident},
                    partial=True,
                )
                if single is not None and single.get("issue"):
                    all_issues.append(single["issue"])
    out(all_issues, args.pretty)


def _resolve_identifiers_to_uuids(identifiers):
    """Resolve issue identifiers (e.g. ENG-123) to UUIDs via batch query."""
    uuids = []
    # Linear's issue() query accepts identifiers directly — batch in groups of 10
    # using GraphQL aliases to avoid multiple round trips
    for i in range(0, len(identifiers), 10):
        batch = identifiers[i : i + 10]
        parts = []
        for j, ident in enumerate(batch):
            parts.append(
                f'i{j}: issue(id: "{ident}") {{ id identifier }}'
            )
        query = "query { " + " ".join(parts) + " }"
        data = graphql(query)
        for j, ident in enumerate(batch):
            result = data.get(f"i{j}")
            if not result:
                print(f"Error: Issue '{ident}' not found.", file=sys.stderr)
                sys.exit(1)
            uuids.append(result["id"])
    return uuids


def cmd_batch_update(args):
    """Batch update multiple issues with the same changes (max 250)."""
    if len(args.identifiers) > 250:
        _die("batch-update supports a maximum of 250 issues per call")
    # Resolve identifiers to UUIDs
    uuids = _resolve_identifiers_to_uuids(args.identifiers)

    inp = {}
    if args.title:
        inp["title"] = args.title
    if args.description:
        inp["description"] = args.description
    if args.state_id:
        inp["stateId"] = args.state_id
    if args.assignee_id:
        inp["assigneeId"] = args.assignee_id
    if args.priority is not None:
        inp["priority"] = args.priority
    if args.label_ids:
        inp["labelIds"] = args.label_ids
    if args.add_label_ids:
        inp["addedLabelIds"] = args.add_label_ids
    if args.remove_label_ids:
        inp["removedLabelIds"] = args.remove_label_ids
    if args.project_id:
        inp["projectId"] = args.project_id
    if args.cycle_id:
        inp["cycleId"] = args.cycle_id
    if args.estimate is not None:
        inp["estimate"] = args.estimate
    if args.parent_id:
        inp["parentId"] = args.parent_id
    if args.due_date:
        inp["dueDate"] = args.due_date

    if not inp:
        print("Error: provide at least one field to update.", file=sys.stderr)
        sys.exit(1)

    data = graphql(
        """
        mutation($ids: [UUID!]!, $input: IssueUpdateInput!) {
            issueBatchUpdate(ids: $ids, input: $input) {
                success
                issues {
                    id identifier title url
                    state { name }
                    assignee { name }
                }
            }
        }
        """,
        {"ids": uuids, "input": inp},
    )
    out(data["issueBatchUpdate"], args.pretty)


def cmd_batch_create(args):
    """Batch create multiple issues from a JSON file or stdin."""
    if args.json_file == "-":
        raw = sys.stdin.read()
    else:
        with open(args.json_file) as f:
            raw = f.read()

    issues = json.loads(raw)
    if not isinstance(issues, list):
        print("Error: JSON input must be an array of issue objects.", file=sys.stderr)
        sys.exit(1)

    # Validate each issue has required fields
    for i, issue in enumerate(issues):
        if "teamId" not in issue:
            print(f"Error: Issue at index {i} missing required field 'teamId'.", file=sys.stderr)
            sys.exit(1)
        if "title" not in issue:
            print(f"Error: Issue at index {i} missing required field 'title'.", file=sys.stderr)
            sys.exit(1)

    data = graphql(
        """
        mutation($input: IssueBatchCreateInput!) {
            issueBatchCreate(input: $input) {
                success
                issues {
                    id identifier title url
                    state { name }
                    assignee { name }
                    team { key }
                }
            }
        }
        """,
        {"input": {"issues": issues}},
    )
    out(data["issueBatchCreate"], args.pretty)


def cmd_create_cycle(args):
    """Create a new cycle/sprint."""
    inp = {
        "teamId": args.team_id,
        "startsAt": args.starts,
        "endsAt": args.ends,
    }
    if args.name:
        inp["name"] = args.name

    data = graphql(
        """
        mutation($input: CycleCreateInput!) {
            cycleCreate(input: $input) {
                success
                cycle { id name number startsAt endsAt team { key } }
            }
        }
        """,
        {"input": inp},
    )
    out(data["cycleCreate"], args.pretty)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Linear API client (stdlib, no deps)"
    )
    parser.add_argument(
        "--pretty", "-p", action="store_true", help="Pretty-print JSON"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- read commands --
    sub.add_parser("me", help="Authenticated user info")
    sub.add_parser("teams", help="List teams")

    p = sub.add_parser("states", help="List workflow states")
    p.add_argument("--team", "-t", help="Filter by team key (e.g. ENG)")

    sub.add_parser("labels", help="List labels")

    p = sub.add_parser("cycles", help="List cycles")
    p.add_argument("--team", "-t", help="Filter by team key")
    p.add_argument("--limit", "-l", type=int, default=10)

    sub.add_parser("users", help="List all users")

    p = sub.add_parser("projects", help="List projects")
    p.add_argument("--limit", "-l", type=int, default=25)

    p = sub.add_parser("issue", help="Get issue details")
    p.add_argument("identifier", help="Issue identifier (e.g. ENG-123)")

    p = sub.add_parser("issues", help="List/filter issues")
    p.add_argument("--team", "-t", help="Team key")
    p.add_argument("--state", "-s", nargs="+", help="State name(s)")
    p.add_argument("--assignee", "-a", help="Assignee name (partial)")
    p.add_argument("--label", nargs="+", help="Label name(s)")
    p.add_argument("--priority", type=int, help="Max priority (1=urgent..4=low)")
    p.add_argument("--project", help="Project name (partial)")
    p.add_argument("--cycle", help="Cycle name (partial)")
    p.add_argument("--limit", "-l", type=int, default=50)
    p.add_argument("--after", help="Pagination cursor")

    p = sub.add_parser("search", help="Search issues by text")
    p.add_argument("query", help="Search text")
    p.add_argument("--limit", "-l", type=int, default=20)

    # -- customer commands (read) --
    p = sub.add_parser("customers", help="List customers")
    p.add_argument("--name", help="Filter by name (partial match)")
    p.add_argument("--tier", help="Filter by tier name or UUID")
    p.add_argument("--status", help="Filter by status name or UUID")
    p.add_argument("--limit", "-l", type=int, default=50)
    p.add_argument("--after", help="Pagination cursor")
    p.add_argument("--include-archived", action="store_true")

    p = sub.add_parser("customer", help="Get a single customer")
    p.add_argument("customer", help="Customer UUID or name")

    p = sub.add_parser("customer-requests", help="List customer requests")
    p.add_argument("--customer", help="Customer name or UUID")
    p.add_argument("--priority", type=int, help="Filter by priority (exact)")
    p.add_argument("--issue-id", help="Filter by linked issue UUID")
    p.add_argument("--limit", "-l", type=int, default=50)
    p.add_argument("--after", help="Pagination cursor")
    p.add_argument("--include-archived", action="store_true")

    p = sub.add_parser("customer-request", help="Get a single customer request")
    p.add_argument("id", help="Customer request UUID")

    p = sub.add_parser("customer-statuses", help="List customer statuses")
    p.add_argument("--include-archived", action="store_true")

    p = sub.add_parser("customer-tiers", help="List customer tiers")
    p.add_argument("--include-archived", action="store_true")

    # -- customer commands (write) --
    p = sub.add_parser("create-customer", help="Create a customer")
    p.add_argument("--name", required=True, help="Customer name")
    p.add_argument("--domains", nargs="+", help="Associated domains")
    p.add_argument("--external-ids", nargs="+", help="External IDs for matching")
    p.add_argument("--owner", help="Owner user name/email or UUID")
    p.add_argument("--status", help="Customer status name or UUID")
    p.add_argument("--tier", help="Customer tier name or UUID")
    p.add_argument("--slack-channel-id", help="Linked Slack channel ID")
    p.add_argument("--revenue", type=int, help="Annual revenue")
    p.add_argument("--size", type=int, help="Company size")

    p = sub.add_parser("update-customer", help="Update a customer")
    p.add_argument("customer", help="Customer UUID or name")
    p.add_argument("--name", help="New customer name")
    p.add_argument("--domains", nargs="+", help="Replace domains")
    p.add_argument("--external-ids", nargs="+", help="Replace external IDs")
    p.add_argument("--owner", help="Owner user (name/email/UUID, empty to clear)")
    p.add_argument("--status", help="Status (name/UUID, empty to clear)")
    p.add_argument("--tier", help="Tier (name/UUID, empty to clear)")
    p.add_argument("--slack-channel-id", help="Slack channel ID (empty to clear)")
    p.add_argument("--revenue", type=int, help="Annual revenue")
    p.add_argument("--size", type=int, help="Company size")

    # -- write commands --
    p = sub.add_parser("create-issue", help="Create an issue")
    p.add_argument("--team-id", required=True, help="Team UUID")
    p.add_argument("--title", required=True)
    p.add_argument("--description", "-d")
    p.add_argument("--assignee-id")
    p.add_argument("--state-id")
    p.add_argument("--label-ids", nargs="+")
    p.add_argument("--priority", type=int, help="0=none 1=urgent 2=high 3=med 4=low")
    p.add_argument("--project-id")
    p.add_argument("--cycle-id")
    p.add_argument("--estimate", type=int)
    p.add_argument("--parent-id", help="Parent issue ID (sub-issues)")

    p = sub.add_parser("update-issue", help="Update an issue")
    p.add_argument("identifier", help="Issue identifier (e.g. ENG-123)")
    p.add_argument("--title")
    p.add_argument("--description", "-d")
    p.add_argument("--state-id")
    p.add_argument("--assignee-id")
    p.add_argument("--priority", type=int)
    p.add_argument("--label-ids", nargs="+")
    p.add_argument("--project-id")
    p.add_argument("--cycle-id")
    p.add_argument("--estimate", type=int)
    p.add_argument("--parent-id")

    p = sub.add_parser("archive-issue", help="Archive an issue")
    p.add_argument("identifier", help="Issue identifier")

    p = sub.add_parser("comment", help="Add comment to an issue")
    p.add_argument("--issue-id", required=True, help="Issue UUID")
    p.add_argument("--body", "-b", required=True, help="Comment body (markdown)")

    p = sub.add_parser("create-relation", help="Create issue relation")
    p.add_argument("--issue-id", required=True, help="Source issue UUID")
    p.add_argument("--related-issue-id", required=True, help="Related issue UUID")
    p.add_argument(
        "--type",
        required=True,
        choices=["blocks", "duplicate", "related"],
        help="Relation type",
    )

    p = sub.add_parser("create-project", help="Create a project")
    p.add_argument("--name", required=True)
    p.add_argument("--team-ids", required=True, nargs="+", help="Team UUID(s)")
    p.add_argument("--description", "-d")
    p.add_argument("--lead-id", help="Lead user UUID")
    p.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    p.add_argument("--target-date", help="Target date (YYYY-MM-DD)")

    p = sub.add_parser("project-updates", help="List project updates")
    p.add_argument("project", help="Project name (partial match) or UUID")
    p.add_argument("--limit", "-l", type=int, default=25)
    p.add_argument("--after", help="Pagination cursor")
    p.add_argument("--order-by", choices=["createdAt", "updatedAt"], default="updatedAt")
    p.add_argument("--include-archived", action="store_true")

    p = sub.add_parser("project-update", help="Get a single project update")
    p.add_argument("id", help="Project update UUID")

    p = sub.add_parser("create-project-update", help="Create a project update")
    p.add_argument("--project", required=True, help="Project name or UUID")
    p.add_argument("--body", "-b", required=True, help="Update body (markdown)")
    p.add_argument("--health", choices=["onTrack", "atRisk", "offTrack"], help="Health status")
    p.add_argument("--hide-diff", action="store_true", help="Hide the diff for this update")

    p = sub.add_parser("update-project-update", help="Update an existing project update")
    p.add_argument("id", help="Project update UUID")
    p.add_argument("--body", "-b", help="Updated body (markdown)")
    p.add_argument("--health", choices=["onTrack", "atRisk", "offTrack"])
    p.add_argument("--hide-diff", type=bool, default=None, help="Hide/show diff")

    p = sub.add_parser("delete-project-update", help="Delete a project update")
    p.add_argument("id", help="Project update UUID")

    p = sub.add_parser("attach-url", help="Attach a URL to an issue")
    p.add_argument("--issue-id", required=True, help="Issue UUID or identifier (e.g. ENG-123)")
    p.add_argument("--url", required=True, help="URL to attach")
    p.add_argument("--title", required=True, help="Display title for the attachment")
    p.add_argument("--subtitle", help="Subtitle text")
    p.add_argument("--icon-url", help="Icon URL for the attachment")

    p = sub.add_parser("attach-slack", help="Link a Slack message to an issue")
    p.add_argument("--issue-id", required=True, help="Issue UUID or identifier (e.g. ENG-123)")
    p.add_argument("--url", required=True, help="Slack message URL")
    p.add_argument("--title", help="Display title (optional, Linear auto-generates from Slack)")
    p.add_argument("--sync", action="store_true", help="Sync Slack thread with Linear comment thread (bidirectional)")

    p = sub.add_parser("batch-get", help="Fetch multiple issues by identifier")
    p.add_argument("identifiers", nargs="+", help="Issue identifiers (e.g. ENG-123 ENG-124)")

    p = sub.add_parser("batch-update", help="Batch update multiple issues")
    p.add_argument("identifiers", nargs="+", help="Issue identifiers (e.g. ENG-123 ENG-124)")
    p.add_argument("--title")
    p.add_argument("--description", "-d")
    p.add_argument("--state-id")
    p.add_argument("--assignee-id")
    p.add_argument("--priority", type=int)
    p.add_argument("--label-ids", nargs="+", help="Replace all labels (UUIDs)")
    p.add_argument("--add-label-ids", nargs="+", help="Add labels without removing existing")
    p.add_argument("--remove-label-ids", nargs="+", help="Remove specific labels")
    p.add_argument("--project-id")
    p.add_argument("--cycle-id")
    p.add_argument("--estimate", type=int)
    p.add_argument("--parent-id")
    p.add_argument("--due-date", help="Due date (YYYY-MM-DD)")

    p = sub.add_parser("batch-create", help="Batch create issues from JSON")
    p.add_argument("json_file", help="Path to JSON file (array of issue objects) or '-' for stdin")

    p = sub.add_parser("create-cycle", help="Create a cycle/sprint")
    p.add_argument("--team-id", required=True, help="Team UUID")
    p.add_argument("--starts", required=True, help="Start date (ISO 8601)")
    p.add_argument("--ends", required=True, help="End date (ISO 8601)")
    p.add_argument("--name")

    args = parser.parse_args()

    cmd_map = {
        "me": cmd_me,
        "teams": cmd_teams,
        "states": cmd_states,
        "labels": cmd_labels,
        "cycles": cmd_cycles,
        "projects": cmd_projects,
        "issue": cmd_issue,
        "issues": cmd_issues,
        "search": cmd_search,
        "customers": cmd_customers,
        "customer": cmd_customer,
        "customer-requests": cmd_customer_requests,
        "customer-request": cmd_customer_request,
        "customer-statuses": cmd_customer_statuses,
        "customer-tiers": cmd_customer_tiers,
        "create-customer": cmd_create_customer,
        "update-customer": cmd_update_customer,
        "create-issue": cmd_create_issue,
        "update-issue": cmd_update_issue,
        "archive-issue": cmd_archive_issue,
        "comment": cmd_comment,
        "users": cmd_users,
        "create-relation": cmd_create_relation,
        "create-project": cmd_create_project,
        "create-cycle": cmd_create_cycle,
        "project-updates": cmd_project_updates,
        "project-update": cmd_project_update,
        "create-project-update": cmd_create_project_update,
        "update-project-update": cmd_update_project_update,
        "delete-project-update": cmd_delete_project_update,
        "attach-url": cmd_attach_url,
        "attach-slack": cmd_attach_slack,
        "batch-get": cmd_batch_get,
        "batch-update": cmd_batch_update,
        "batch-create": cmd_batch_create,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
