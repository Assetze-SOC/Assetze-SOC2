# tools/github_verifier.py
import requests
import json
from langchain_core.tools import tool

@tool
def verify_github_token_api(token: str) -> str:
    """
    Verifies a GitHub personal access token by attempting a simple API call
    and returns its validity, scopes, and a message as a JSON string.
    Input is the GitHub token string.
    """
    api_url = "https://api.github.com/user"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        response_data = {}
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            # Handle cases where response might not be JSON (e.g., HTML error pages)
            response_data = {"message": response.text[:200] + "..." if response.text else "No JSON response body"}

        if response.status_code == 200:
            scopes = response.headers.get('X-OAuth-Scopes', '').split(', ')
            scopes = [s.strip() for s in scopes if s.strip()] # Filter out empty strings and trim whitespace
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
                "message": f"Token is invalid or expired: {response_data.get('message', 'Bad credentials')}",
                "status_code": response.status_code
            }
        elif response.status_code == 403:
            # Could be rate limit, invalid token, or insufficient permissions for this endpoint
            message = response_data.get('message', 'Access Forbidden.')
            if "rate limit" in message.lower():
                message = f"Rate limit exceeded or forbidden: {message}"
            elif "resource not accessible by integration" in message.lower() or "requires authentication" in message.lower():
                message = f"Token forbidden or insufficient permissions: {message}"
            result = {
                "valid": False,
                "scopes": [],
                "message": message,
                "status_code": response.status_code
            }
        else:
            result = {
                "valid": False,
                "scopes": [],
                "message": f"Unexpected API response (Status: {response.status_code}): {response_data.get('message', 'No message')}",
                "status_code": response.status_code
            }
    except requests.exceptions.Timeout:
        result = {
            "valid": False,
            "scopes": [],
            "message": "Request timed out when connecting to GitHub API.",
            "status_code": -1
        }
    except requests.exceptions.RequestException as e:
        result = {
            "valid": False,
            "scopes": [],
            "message": f"Network or API request error: {e}",
            "status_code": -2
        }
    except Exception as e:
        result = {
            "valid": False,
            "scopes": [],
            "message": f"An unexpected error occurred during tool execution: {e}",
            "status_code": -99
        }
    return json.dumps(result)