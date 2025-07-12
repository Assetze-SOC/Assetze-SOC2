import requests
import os
import json
import csv
import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Common Headers for GitHub API ---
GITHUB_API_HEADERS = {
    "Accept": "application/vnd.github.com+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

# --- Function to Verify Dependabot Status (Existing, with minor refinement) ---
def verify_dependabot_status(token: str, owner: str, repo: str) -> dict:
    """
    Checks if Dependabot vulnerability alerts are enabled for a given GitHub repository.
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}/vulnerability-alerts"
    headers = {"Authorization": f"token {token}", **GITHUB_API_HEADERS}

    print(f"Checking Dependabot status for: {owner}/{repo}...")

    result = {
        "owner": owner,
        "repo_name": repo,
        "enabled": False,
        "status_text": "Unknown Error",
        "message": "An unexpected error occurred before API call.",
        "status_code": 0,
        "error_details": ""
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=15)

        if response.status_code == 204:
            result["enabled"] = True
            result["status_text"] = "Enabled"
            result["message"] = f"Dependabot vulnerability alerts are ENABLED for {owner}/{repo}."
            result["status_code"] = response.status_code
        elif response.status_code == 404:
            result["enabled"] = False
            result["status_text"] = "Disabled/Not Found"
            result["message"] = f"Dependabot vulnerability alerts are DISABLED for {owner}/{repo} or repository not found."
            result["status_code"] = response.status_code
        elif response.status_code == 403:
            error_message = response.json().get("message", "Forbidden: Check token scope or access.")
            result["enabled"] = False
            result["status_text"] = "Error: Forbidden"
            result["message"] = f"Forbidden: {error_message}. Check token scopes ('repo' or 'public_repo') and access."
            result["status_code"] = response.status_code
        else:
            error_details_msg = f"Unexpected HTTP status code: {response.status_code}"
            try:
                response_json = response.json()
                if "message" in response_json:
                    error_details_msg += f" - Message: {response_json['message']}"
            except json.JSONDecodeError:
                error_details_msg += f" - Response body: {response.text[:200]}..."
            
            result["enabled"] = False
            result["status_text"] = "Error: API Response Issue"
            result["message"] = f"Could not determine Dependabot status: {error_details_msg}"
            result["status_code"] = response.status_code

    except requests.exceptions.Timeout:
        result["status_text"] = "Error: Timeout"
        result["message"] = "Request timed out when connecting to GitHub API. Check network or API availability."
        result["status_code"] = -1
        result["error_details"] = "Timeout"
    except requests.exceptions.ConnectionError as e:
        result["status_text"] = "Error: Connection"
        result["message"] = f"Network connection error: Could not reach GitHub API. Details: {e}"
        result["status_code"] = -2
        result["error_details"] = str(e)
    except requests.exceptions.RequestException as e:
        result["status_text"] = "Error: Request Failed"
        result["message"] = f"An error occurred during the API request: {e}"
        result["status_code"] = -3
        result["error_details"] = str(e)
    except Exception as e:
        result["status_text"] = "Error: Unexpected"
        result["message"] = f"An unexpected error occurred: {e}"
        result["status_code"] = -99
        result["error_details"] = str(e)
    
    return result

# --- Function to Get Organization Member Roles (Existing) ---
def get_organization_roles_to_csv(token: str, organization_name: str, output_prefix: str = "github_org_roles") -> bool:
    """
    Fetches all members and their overall organization roles for a given GitHub organization and saves to a CSV.
    Returns True if data was successfully fetched and written, False otherwise.
    """
    print(f"\n--- Fetching overall roles for organization: {organization_name} ---")
    members_data = []
    page = 1
    per_page = 100
    headers = {"Authorization": f"token {token}", **GITHUB_API_HEADERS}
    org_roles_auditable = False # Flag for summary report

    try:
        while True:
            api_url = f"https://api.github.com/orgs/{organization_name}/members?page={page}&per_page={per_page}"
            print(f"  Fetching page {page} from {api_url}...")
            response = requests.get(api_url, headers=headers, timeout=20)

            if response.status_code == 200:
                current_page_members = response.json()
                if not current_page_members:
                    break

                for member in current_page_members:
                    members_data.append({
                        "Organization": organization_name,
                        "Username": member.get("login"),
                        "Role": member.get("role")
                    })
                
                if 'Link' in response.headers and 'rel="next"' in response.headers['Link']:
                    page += 1
                else:
                    break
            elif response.status_code == 403:
                error_msg = response.json().get("message", "Forbidden: Check token scope or organization access.")
                print(f"Error 403: {error_msg}")
                print("  Ensure your GitHub token has 'read:org' scope for this organization.")
                break
            elif response.status_code == 404:
                print(f"Error 404: Organization '{organization_name}' not found or no members accessible.")
                break
            else:
                print(f"Unexpected HTTP status code {response.status_code}: {response.text}")
                break

    except requests.exceptions.RequestException as e:
        print(f"Network or API request error while fetching organization roles: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while fetching organization roles: {e}")

    if not members_data:
        print(f"No overall member data fetched for organization '{organization_name}'. Skipping CSV creation.")
        return False # Indicate failure to audit roles

    # Generate a unique CSV filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{output_prefix}_{organization_name}_org_roles_{timestamp}.csv" # Specific filename

    csv_headers = ["Organization", "Username", "Role"]

    print(f"--- Writing overall organization roles to {csv_filename} ---")
    try:
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            writer.writeheader()
            writer.writerows(members_data)
        print(f"Successfully wrote overall organization roles to {csv_filename}")
        org_roles_auditable = True
    except IOError as e:
        print(f"Error writing CSV file {csv_filename}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while writing organization roles CSV: {e}")
    
    return org_roles_auditable

# --- NEW: Function to Get Team Member Roles ---
def get_team_member_roles_to_csv(token: str, organization_name: str, output_prefix: str = "github_team_roles") -> bool:
    """
    Fetches all teams and their members with their roles within each team, then saves to a CSV.
    Requires 'read:org' scope.
    Returns True if data was successfully fetched and written, False otherwise.
    """
    print(f"\n--- Fetching team members and roles for organization: {organization_name} ---")
    team_members_data = []
    
    # First, get all teams in the organization
    teams_url = f"https://api.github.com/orgs/{organization_name}/teams"
    headers = {"Authorization": f"token {token}", **GITHUB_API_HEADERS}
    
    teams_page = 1
    teams = []

    try:
        while True:
            response = requests.get(f"{teams_url}?page={teams_page}&per_page=100", headers=headers, timeout=20)
            if response.status_code == 200:
                current_teams = response.json()
                if not current_teams:
                    break
                teams.extend(current_teams)
                if 'Link' in response.headers and 'rel="next"' in response.headers['Link']:
                    teams_page += 1
                else:
                    break
            elif response.status_code == 403:
                error_msg = response.json().get("message", "Forbidden: Check token scope or organization access.")
                print(f"Error 403 fetching teams: {error_msg}")
                print("  Ensure your GitHub token has 'read:org' scope for this organization.")
                return False
            elif response.status_code == 404:
                print(f"Error 404 fetching teams: Organization '{organization_name}' not found or no teams accessible.")
                return False
            else:
                print(f"Unexpected HTTP status code {response.status_code} fetching teams: {response.text}")
                return False
    except requests.exceptions.RequestException as e:
        print(f"Network or API request error while fetching teams: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while fetching teams: {e}")
        return False

    if not teams:
        print(f"No teams found for organization '{organization_name}'. Skipping team member roles CSV creation.")
        return False

    # Now, for each team, get its members
    for team in teams:
        team_slug = team.get("slug")
        team_name = team.get("name")
        print(f"  Fetching members for team: {team_name} ({team_slug})...")
        
        members_page = 1
        team_members_url = f"https://api.github.com/orgs/{organization_name}/teams/{team_slug}/members"
        
        try:
            while True:
                member_response = requests.get(f"{team_members_url}?page={members_page}&per_page=100", headers=headers, timeout=20)
                if member_response.status_code == 200:
                    current_members = member_response.json()
                    if not current_members:
                        break
                    
                    for member in current_members:
                        team_members_data.append({
                            "Organization": organization_name,
                            "Team Name": team_name,
                            "Username": member.get("login"),
                            "Team Role": member.get("role") # 'member' or 'maintainer'
                        })
                    
                    if 'Link' in member_response.headers and 'rel="next"' in member_response.headers['Link']:
                        members_page += 1
                    else:
                        break
                elif member_response.status_code == 403:
                    error_msg = member_response.json().get("message", "Forbidden: Check token scope.")
                    print(f"Error 403 fetching members for team {team_name}: {error_msg}")
                    break # Stop processing this team
                else:
                    print(f"Unexpected HTTP status code {member_response.status_code} for team {team_name} members: {member_response.text}")
                    break # Stop processing this team
        except requests.exceptions.RequestException as e:
            print(f"Network or API request error fetching members for team {team_name}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred fetching members for team {team_name}: {e}")

    if not team_members_data:
        print(f"No team member data fetched for organization '{organization_name}'. Skipping CSV creation.")
        return False

    # Generate a unique CSV filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{output_prefix}_{organization_name}_team_roles_{timestamp}.csv" # Specific filename

    csv_headers = ["Organization", "Team Name", "Username", "Team Role"]

    print(f"--- Writing team members and roles to {csv_filename} ---")
    try:
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            writer.writeheader()
            writer.writerows(team_members_data)
        print(f"Successfully wrote team members and roles to {csv_filename}")
        return True
    except IOError as e:
        print(f"Error writing CSV file {csv_filename}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while writing team members CSV: {e}")
        return False

# --- NEW: Function to Generate Security Posture Summary ---
def generate_security_posture_summary_csv(
    organization_name: str,
    all_dependabot_results: list[dict],
    org_roles_auditable: bool,
    team_roles_auditable: bool,
    output_prefix: str = "github_audit_report"
) -> None:
    """
    Generates a summary CSV report of the security posture.
    """
    print(f"\n--- Generating Security Posture Summary for {organization_name} ---")
    
    summary_data = []

    # 1. Dependabot Summary
    total_repos = len(all_dependabot_results)
    enabled_dependabot_repos = sum(1 for r in all_dependabot_results if r.get("enabled", False))
    dependabot_percentage = (enabled_dependabot_repos / total_repos * 100) if total_repos > 0 else 0

    dependabot_summary_text = (
        f"{enabled_dependabot_repos}/{total_repos} repositories have Dependabot enabled "
        f"({dependabot_percentage:.2f}% coverage)."
    )
    if total_repos == 0:
        dependabot_summary_text = "No repositories were checked for Dependabot status."
    elif dependabot_percentage < 100:
        dependabot_summary_text += " Consider enabling Dependabot on all relevant repositories."
    else:
        dependabot_summary_text += " Excellent coverage!"

    # 2. Roles Summary
    roles_summary_text = "Organization overall roles successfully audited." if org_roles_auditable else "Failed to audit organization overall roles. Check token permissions or organization existence."
    team_roles_summary_text = "Organization team roles successfully audited." if team_roles_auditable else "Failed to audit organization team roles (or no teams/members found). Check token permissions or organization teams."

    # General comments/actions
    overall_comments = []
    if dependabot_percentage < 100 and total_repos > 0:
        overall_comments.append("Action: Improve Dependabot coverage.")
    if not org_roles_auditable or not team_roles_auditable:
        overall_comments.append("Action: Verify GitHub token permissions ('read:org') and organization membership to audit roles.")
    if not overall_comments:
        overall_comments.append("Current posture appears well-audited based on checks performed.")


    summary_row = {
        "Organization": organization_name,
        "Dependabot Coverage": dependabot_summary_text,
        "Org Roles Auditable": "Yes" if org_roles_auditable else "No",
        "Team Roles Auditable": "Yes" if team_roles_auditable else "No",
        "Recommended Actions": "; ".join(overall_comments)
    }
    summary_data.append(summary_row)

    # Generate a unique CSV filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{output_prefix}_{organization_name}_security_summary_{timestamp}.csv"

    csv_headers = [
        "Organization",
        "Dependabot Coverage",
        "Org Roles Auditable",
        "Team Roles Auditable",
        "Recommended Actions"
    ]

    print(f"--- Writing security posture summary to {csv_filename} ---")
    try:
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            writer.writeheader()
            writer.writerows(summary_data)
        print(f"Successfully wrote security posture summary to {csv_filename}")
    except IOError as e:
        print(f"Error writing summary CSV file {csv_filename}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while writing summary CSV: {e}")


# --- Main Execution Block ---
if __name__ == "__main__":
    github_token = os.getenv("GITHUB_TOKEN")
    repositories_str = os.getenv("GITHUB_REPOSITORIES")
    github_organization = os.getenv("GITHUB_ORGANIZATION")
    output_csv_prefix = os.getenv("OUTPUT_CSV_PREFIX", "github_audit_report")

    if not github_token:
        print("Error: GITHUB_TOKEN environment variable not set.")
        print("Please create a .env file or set the environment variable.")
        exit(1)

    all_dependabot_results = []
    org_roles_success = False
    team_roles_success = False

    # --- 1. Dependabot Status Check ---
    if repositories_str:
        repositories_to_check = []
        for repo_full_name in repositories_str.split(','):
            repo_full_name = repo_full_name.strip()
            if '/' in repo_full_name:
                owner, repo_name = repo_full_name.split('/', 1)
                repositories_to_check.append((owner, repo_name))
            else:
                print(f"Warning: Skipping malformed repository entry: '{repo_full_name}'. Expected format 'owner/repo'.")

        if repositories_to_check:
            print("\n--- Starting Dependabot Status Checks for Multiple Repositories ---")
            for owner, repo_name in repositories_to_check:
                result = verify_dependabot_status(github_token, owner, repo_name)
                all_dependabot_results.append(result)
                print(f"  {owner}/{repo_name}: {result['status_text']}")

            # Generate CSV for Dependabot status
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            dependabot_csv_filename = f"{output_csv_prefix}_dependabot_status_{timestamp}.csv"
            csv_headers_dependabot = ["Organization", "Repository Name", "Dependabot Status", "Detailed Message", "HTTP Status Code"]

            print(f"\n--- Writing Dependabot status results to {dependabot_csv_filename} ---")
            try:
                with open(dependabot_csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(csv_headers_dependabot)
                    for res in all_dependabot_results:
                        writer.writerow([
                            res["owner"],
                            res["repo_name"],
                            res["status_text"],
                            res["message"],
                            res["status_code"]
                        ])
                print(f"Successfully wrote Dependabot status results to {dependabot_csv_filename}")
            except IOError as e:
                print(f"Error writing Dependabot CSV file {dependabot_csv_filename}: {e}")
            except Exception as e:
                print(f"An unexpected error occurred while writing Dependabot CSV: {e}")
        else:
            print("\nNo repositories specified for Dependabot check. Skipping.")
    else:
        print("\nNo GITHUB_REPOSITORIES specified. Skipping Dependabot check.")


    # --- 2. Organization Overall Roles Check ---
    if github_organization:
        org_roles_success = get_organization_roles_to_csv(github_token, github_organization, output_csv_prefix)
    else:
        print("\nNo GITHUB_ORGANIZATION specified for overall roles. Skipping.")

    # --- 3. NEW: Organization Team Member Roles Check ---
    if github_organization:
        team_roles_success = get_team_member_roles_to_csv(github_token, github_organization, output_csv_prefix)
    else:
        print("\nNo GITHUB_ORGANIZATION specified for team roles. Skipping.")

    # --- 4. NEW: Security Posture Summary Report ---
    if github_organization or all_dependabot_results:
        # Only generate if there's *some* data or an organization specified
        generate_security_posture_summary_csv(
            github_organization if github_organization else "N/A", # Pass org name even if not explicitly set for repos
            all_dependabot_results,
            org_roles_success,
            team_roles_success,
            output_csv_prefix
        )
    else:
        print("\nNo data to generate Security Posture Summary. Skipping.")

    print("\n--- All Audits Complete ---")
    print("Remember to verify your GitHub token has the necessary permissions:")
    print("  For Dependabot: 'repo' scope (private) or 'public_repo' (public).")
    print("  For Organization Roles and Team Roles: 'read:org' scope.")