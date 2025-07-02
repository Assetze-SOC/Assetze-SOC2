# workflow_state.py
from typing import TypedDict, List, Dict, Any, Optional

class GithubTokenVerificationState(TypedDict):
    """
    Represents the state of the GitHub token verification workflow.
    """
    token: str  # The GitHub token to verify
    verification_result: Optional[Dict[str, Any]]  # Raw result from the GitHub API tool
    analysis_message: Optional[str]  # LLM's analysis of the verification result
    remediation_suggestions: Optional[str] # LLM's suggestions for fixing issues