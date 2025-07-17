import requests
import os
import csv
import datetime
from dotenv import load_dotenv

load_dotenv()

GITHUB_API_URL = "https://api.github.com"
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}


def fetch_paginated(endpoint, token):
    """Helper to fetch paginated API results."""
    results = []
    page = 1
    headers = {"Authorization": f"token {token}", **GITHUB_HEADERS}

    while True:
        resp = requests.get(f"{endpoint}?page={page}&per_page=100", headers=headers, timeout=15)
        if resp.status_code != 200:
            raise Exception(f"API error: {resp.status_code} - {resp.text}")
        data = resp.json()
        if not data:
            break
        results.extend(data)
        if 'Link' not in resp.headers or 'rel="next"' not in resp.headers['Link']:
            break
        page += 1

    return results


def fetch_org_members(org, token):
    """Fetch org members and their roles."""
    print(f"Fetching organization members for: {org}")
    endpoint = f"{GITHUB_API_URL}/orgs/{org}/members"
    members = fetch_paginated(endpoint, token)

    member_roles = []
    for member in members:
        username = member.get("login")
        role_endpoint = f"{GITHUB_API_URL}/orgs/{org}/memberships/{username}"
        resp = requests.get(role_endpoint, headers={"Authorization": f"token {token}", **GITHUB_HEADERS}, timeout=10)
        role = "unknown"
        if resp.status_code == 200:
            role = resp.json().get("role", "unknown")
        member_roles.append({
            "Organization": org,
            "Username": username,
            "Role": role
        })

    return member_roles


def fetch_team_members(org, token):
    """Fetch teams and their members/roles."""
    print(f"Fetching teams for: {org}")
    teams_endpoint = f"{GITHUB_API_URL}/orgs/{org}/teams"
    teams = fetch_paginated(teams_endpoint, token)

    team_roles = []
    for team in teams:
        slug = team.get("slug")
        name = team.get("name")
        print(f"  Fetching members for team: {name} ({slug})")

        members_endpoint = f"{GITHUB_API_URL}/orgs/{org}/teams/{slug}/memberships"
        members = fetch_paginated(members_endpoint, token)

        for member in members:
            username = member.get("user", {}).get("login")
            role = member.get("role", "member")
            team_roles.append({
                "Organization": org,
                "Team Name": name,
                "Username": username,
                "Team Role": role
            })

    return team_roles


def write_csv(filename, data, headers):
    """Write data to CSV file."""
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
    print(f"✅ Data written to {filename}")


if __name__ == "__main__":
    github_token = os.getenv("GITHUB_TOKEN")
    github_org = os.getenv("GITHUB_ORGANIZATION")
    prefix = os.getenv("OUTPUT_CSV_PREFIX", "github_audit")

    if not github_token or not github_org:
        print("❌ Please set GITHUB_TOKEN and GITHUB_ORGANIZATION in your .env file.")
        exit(1)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Org members & roles
    try:
        org_members = fetch_org_members(github_org, github_token)
        org_filename = f"{prefix}_{github_org}_org_members_{timestamp}.csv"
        write_csv(org_filename, org_members, ["Organization", "Username", "Role"])
    except Exception as e:
        print(f"Error fetching org members: {e}")

    # Team members & roles
    try:
        team_members = fetch_team_members(github_org, github_token)
        team_filename = f"{prefix}_{github_org}_team_members_{timestamp}.csv"
        write_csv(team_filename, team_members, ["Organization", "Team Name", "Username", "Team Role"])
    except Exception as e:
        print(f"Error fetching team members: {e}")

    print("\n🎯 Done. Make sure your token has at least `read:org` scope.")
