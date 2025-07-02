# github_token_verifier.py
import requests
from langchain.tools import tool
import json

@tool
def verify_github_token_tool(token: str) -> str:
    """
    Verifies a GitHub personal access token and returns its validity and scopes as a JSON string.
    Input is the GitHub token string.
    """
    api_url = "https://api.github.com/user"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        response = requests.get(api_url, headers=headers)
        response_data = response.json()

        if response.status_code == 200:
            scopes = response.headers.get('X-OAuth-Scopes', '').split(', ')
            scopes = [s for s in scopes if s] # Filter out empty strings
            result = {
                "valid": True,
                "scopes": scopes,
                "message": "Token is valid.",
                "status_code": response.status_code
            }
        elif response.status_code == 401:
            result = {
                "valid": False,
                "scopes": [],
                "message": f"Token is invalid or expired: {response_data.get('message', 'Unknown error')}",
                "status_code": response.status_code
            }
        elif response.status_code == 403:
            result = {
                "valid": False,
                "scopes": [],
                "message": f"Token access forbidden (e.g., rate limited or token permissions): {response_data.get('message', 'Unknown error')}",
                "status_code": response.status_code
            }
        else:
            result = {
                "valid": False,
                "scopes": [],
                "message": f"Unexpected API response (Status: {response.status_code}): {response_data.get('message', 'No message')}",
                "status_code": response.status_code
            }
    except requests.exceptions.RequestException as e:
        result = {
            "valid": False,
            "scopes": [],
            "message": f"Network or API request error: {e}",
            "status_code": -1
        }
    except json.JSONDecodeError:
        result = {
            "valid": False,
            "scopes": [],
            "message": "JSON Decode Error: Unexpected response format from GitHub API.",
            "status_code": -3
        }
    except Exception as e:
        result = {
            "valid": False,
            "scopes": [],
            "message": f"An unexpected error occurred: {e}",
            "status_code": -4
        }
    return json.dumps(result)

if __name__ == '__main__':
    # Example usage for testing the tool function directly
    # Replace with a real token for actual testing
    token_to_test = "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"
    verification_output = verify_github_token_tool.run(token_to_test)
    print(verification_output)