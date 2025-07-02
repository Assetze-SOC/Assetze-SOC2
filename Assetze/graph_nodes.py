# graph_nodes.py
import json
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from tools.github_verifier import verify_github_token_api
from workflow_state import GithubTokenVerificationState
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables for LLM keys

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0) # gpt-4o-mini is cost-effective for this

def call_github_verifier_node(state: GithubTokenVerificationState) -> GithubTokenVerificationState:
    """
    Node to call the GitHub token verification tool.
    """
    print("Executing: call_github_verifier_node")
    token = state.get("token")
    if not token:
        # This shouldn't happen if the entry point ensures a token, but good to guard
        print("Error: No token provided to verifier node.")
        state["verification_result"] = {"valid": False, "message": "No token provided.", "status_code": 0}
        return state

    try:
        result_json = verify_github_token_api.run(token)
        state["verification_result"] = json.loads(result_json)
        print(f"Verification result: {state['verification_result']}")
    except Exception as e:
        print(f"Error calling GitHub verifier tool: {e}")
        state["verification_result"] = {
            "valid": False,
            "scopes": [],
            "message": f"Error during API call: {e}",
            "status_code": -100
        }
    return state

def analyze_result_node(state: GithubTokenVerificationState) -> GithubTokenVerificationState:
    """
    Node for LLM to analyze the verification result and provide a concise summary.
    """
    print("Executing: analyze_result_node")
    verification_result = state.get("verification_result", {})
    is_valid = verification_result.get("valid")
    message = verification_result.get("message")
    scopes = verification_result.get("scopes")
    status_code = verification_result.get("status_code")

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are an AI assistant analyzing GitHub token verification results. "
                   "Summarize the outcome concisely. State if the token is valid or invalid. "
                   "If valid, list the scopes. If invalid, provide a brief, clear reason. "
                   "Keep the summary to 1-3 sentences."),
        ("human", f"GitHub Token Verification Result:\nValid: {is_valid}\nMessage: {message}\nScopes: {scopes}\nStatus Code: {status_code}")
    ])
    
    chain = prompt_template | llm
    
    try:
        analysis = chain.invoke({"input": ""}).content
        state["analysis_message"] = analysis
        print(f"Analysis: {analysis}")
    except Exception as e:
        print(f"Error during LLM analysis: {e}")
        state["analysis_message"] = f"Error during analysis: {e}"
    
    return state

def suggest_remediation_node(state: GithubTokenVerificationState) -> GithubTokenVerificationState:
    """
    Node for LLM to suggest remediation steps if the token is invalid.
    This node is only triggered if the token is found to be invalid.
    """
    print("Executing: suggest_remediation_node")
    verification_result = state.get("verification_result", {})
    is_valid = verification_result.get("valid")
    message = verification_result.get("message")
    scopes = verification_result.get("scopes") # Will be empty if invalid
    status_code = verification_result.get("status_code")

    if is_valid:
        state["remediation_suggestions"] = "Token is valid. No remediation needed."
        return state

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are an AI assistant providing practical remediation advice for GitHub token issues. "
                   "Based on the error message and status code, suggest concrete, actionable steps to resolve the issue. "
                   "Focus on common problems like expiration, incorrect scopes, or network issues. "
                   "Provide 2-4 distinct suggestions."),
        ("human", f"GitHub Token Invalid. Error Message: '{message}'. Status Code: {status_code}. "
                   "What are the best steps to fix this token issue?")
    ])
    
    chain = prompt_template | llm

    try:
        suggestions = chain.invoke({"input": ""}).content
        state["remediation_suggestions"] = suggestions
        print(f"Remediation suggestions: {suggestions}")
    except Exception as e:
        print(f"Error during LLM remediation suggestion: {e}")
        state["remediation_suggestions"] = f"Error generating suggestions: {e}"
    
    return state

# Define a human-in-the-loop node (optional but good for review)
def human_review_node(state: GithubTokenVerificationState) -> GithubTokenVerificationState:
    """
    (Optional) Node for human review of the token status before taking further action.
    This would typically be implemented in a real application with a UI or notification.
    """
    print("\n--- HUMAN REVIEW REQUIRED ---")
    print(f"Token: {state['token'][:5]}... (first 5 chars)")
    print(f"Validity: {state['verification_result']['valid']}")
    print(f"Analysis: {state['analysis_message']}")
    if not state['verification_result']['valid']:
        print(f"Remediation: {state['remediation_suggestions']}")
    
    # In a real app, this would block and wait for human input/approval
    # For this script, we'll just print and continue
    print("Review complete. Continuing workflow...")
    return state