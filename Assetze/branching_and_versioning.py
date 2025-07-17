import requests
import os
import csv
from datetime import datetime
from dotenv import load_dotenv

# Ensure .env is loaded (if running independently)
load_dotenv()

def get_repository_info_to_csv(token: str, owner: str, repo: str, output_dir: str = "audit_data"):
    """
    Fetches latest branching and version information for a GitHub repository and saves it to CSVs.

    Args:
        token (str): Your GitHub Personal Access Token with 'repo' scope.
        owner (str): The owner (user or organization) of the repository.
        repo (str): The name of the repository.
        output_dir (str): Directory to save the CSV files.
    """
    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.com+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # --- 1. Get Repository Details (for default branch) ---
    repo_details_url = base_url
    print(f"\nFetching repository details for {owner}/{repo}...")
    try:
        response = requests.get(repo_details_url, headers=headers, timeout=10)
        response.raise_for_status()
        repo_data = response.json()

        default_branch = repo_data.get("default_branch")
        print(f"  - Default branch: {default_branch}")

        # --- 2. Get Latest Commit on Default Branch ---
        commit_url = f"{base_url}/commits/{default_branch}"
        print(f"  - Fetching latest commit for default branch ({default_branch})...")
        commit_response = requests.get(commit_url, headers=headers, timeout=10)
        commit_response.raise_for_status()
        latest_commit_data = commit_response.json()

        latest_commit_sha = latest_commit_data.get("sha")
        latest_commit_message = latest_commit_data.get("commit", {}).get("message", "").split('\n')[0]
        latest_commit_date = latest_commit_data.get("commit", {}).get("author", {}).get("date")

        repo_info = {
            "Repository": f"{owner}/{repo}",
            "Default Branch": default_branch,
            "Latest Commit SHA": latest_commit_sha,
            "Latest Commit Message": latest_commit_message,
            "Latest Commit Date": latest_commit_date,
            "Public": not repo_data.get("private"),
            "Description": repo_data.get("description"),
            "Created At": repo_data.get("created_at"),
            "Last Updated At": repo_data.get("updated_at"),
            "Pushed At": repo_data.get("pushed_at"),
            "License": repo_data.get("license", {}).get("spdx_id") if repo_data.get("license") else "N/A"
        }

        output_file_repo_info = os.path.join(output_dir, f"{owner}_{repo}_repo_info.csv")
        with open(output_file_repo_info, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = list(repo_info.keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(repo_info)
        print(f"  - Saved repository info to {output_file_repo_info}")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Error: Repository '{owner}/{repo}' not found.")
        elif e.response.status_code == 403:
            print(f"Error: Forbidden. Insufficient permissions for {owner}/{repo}. Ensure your token has 'repo' scope.")
        else:
            print(f"HTTP Error fetching repo info (HTTP {e.response.status_code}): {e.response.text}")
        return # Exit if repo info fails
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching repo info: {e}")
        return

    # --- 3. Get Latest Release (if any) ---
    releases_url = f"{base_url}/releases/latest"
    print(f"  - Fetching latest release for {owner}/{repo}...")
    try:
        response = requests.get(releases_url, headers=headers, timeout=10)
        if response.status_code == 200:
            latest_release = response.json()
            release_info = {
                "Repository": f"{owner}/{repo}",
                "Release Name": latest_release.get("name"),
                "Tag Name": latest_release.get("tag_name"),
                "Published At": latest_release.get("published_at"),
                "Author": latest_release.get("author", {}).get("login"),
                "Is Pre-release": latest_release.get("prerelease"),
                "Release URL": latest_release.get("html_url")
            }
            output_file_release = os.path.join(output_dir, f"{owner}_{repo}_latest_release.csv")
            with open(output_file_release, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = list(release_info.keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(release_info)
            print(f"  - Saved latest release info to {output_file_release}")
        elif response.status_code == 404:
            print(f"  - No latest release found for {owner}/{repo}.")
        else:
            print(f"  - Error fetching latest release (HTTP {response.status_code}): {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"  - Network error fetching latest release: {e}")

    # --- 4. Get All Branches ---
    branches_url = f"{base_url}/branches"
    all_branches_data = []
    page = 1
    print(f"  - Fetching all branches for {owner}/{repo}...")
    while True:
        params = {"per_page": per_page, "page": page}
        response = requests.get(branches_url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            current_branches = response.json()
            if not current_branches:
                break
            for branch in current_branches:
                all_branches_data.append({
                    "Repository": f"{owner}/{repo}",
                    "Branch Name": branch.get("name"),
                    "Latest Commit SHA": branch.get("commit", {}).get("sha"),
                    "Protected": branch.get("protected"),
                    "URL": branch.get("commit", {}).get("url") # This URL links to commit details, useful for date
                })
            print(f"    - Fetched {len(current_branches)} branches from page {page}")
            page += 1
        else:
            print(f"  - Error fetching branches (HTTP {response.status_code}): {response.text}")
            break

    if all_branches_data:
        output_file_branches = os.path.join(output_dir, f"{owner}_{repo}_branches.csv")
        with open(output_file_branches, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ["Repository", "Branch Name", "Latest Commit SHA", "Protected", "URL"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_branches_data)
        print(f"  - Saved {len(all_branches_data)} branches to {output_file_branches}")
    else:
        print(f"  - No branches found or could not retrieve for {owner}/{repo}.")

# Example usage (can be moved to your main script's `if __name__ == "__main__":` block)
if __name__ == "__main__":
    github_token = os.getenv("GITHUB_TOKEN")
    repo_owner = "Assetze-SOC" # Or your organization name
    repository_name = "Assetze-SOC2" # Replace with the repository you want to check

    if not github_token:
        print("Error: GITHUB_TOKEN not set in .env file.")
    elif not repo_owner or not repository_name:
        print("Error: REPO_OWNER and REPOSITORY_NAME must be set.")
    else:
        get_repository_info_to_csv(github_token, repo_owner, repository_name)