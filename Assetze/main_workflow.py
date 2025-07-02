# main_workflow.py
from langgraph.graph import StateGraph, END
from workflow_state import GithubTokenVerificationState
from graph_nodes import (
    call_github_verifier_node,
    analyze_result_node,
    suggest_remediation_node,
    # human_review_node
)
import os
import webbrowser 
import datetime 

class GithubTokenVerificationWorkflow:
    def __init__(self):
        self.workflow = StateGraph(GithubTokenVerificationState)
        self._build_graph()

    def _build_graph(self):
        # Add nodes
        self.workflow.add_node("verify_token", call_github_verifier_node)
        self.workflow.add_node("analyze_result", analyze_result_node)
        self.workflow.add_node("suggest_remediation", suggest_remediation_node)
        # self.workflow.add_node("human_review", human_review_node) # Uncomment to add human review

        # Define entry point
        self.workflow.set_entry_point("verify_token")

        # Define edges
        self.workflow.add_edge("verify_token", "analyze_result")

        # Conditional edge based on verification result
        self.workflow.add_conditional_edges(
            "analyze_result",
            self._decide_next_step,
            {
                "remediate": "suggest_remediation",
                "end": END # If valid, go directly to end
            }
        )
        self.workflow.add_edge("suggest_remediation", END) # After remediation, end

        # If human_review is added:
        # self.workflow.add_edge("suggest_remediation", "human_review")
        # self.workflow.add_edge("human_review", END)


    def _decide_next_step(self, state: GithubTokenVerificationState) -> str:
        """
        Determines the next step based on the token verification result.
        """
        if state.get("verification_result", {}).get("valid"):
            print("Decision: Token is valid. Ending workflow.")
            return "end"
        else:
            print("Decision: Token is invalid. Proceeding to remediation.")
            return "remediate"

    def run(self, token: str) -> GithubTokenVerificationState:
        """
        Executes the GitHub token verification workflow.
        """
        initial_state = GithubTokenVerificationState(
            token=token,
            verification_result=None,
            analysis_message=None,
            remediation_suggestions=None
        )
        
        compiled_graph = self.workflow.compile()

        # --- NEW: Generate and display Mermaid graph ---
        try:
            mermaid_graph_code = compiled_graph.get_graph().draw_mermaid() # Use .draw_mermaid() for older LangChain versions
            self._display_mermaid_graph(mermaid_graph_code)
        except Exception as e:
            print(f"\n--- Error generating or displaying Mermaid graph: {e} ---")
            print("   Ensure your LangGraph and LangChain versions are compatible for visualization.")
            print("   You might need to install 'mermaid-py' (though LangGraph often bundles what's needed).")
        # --- END NEW ---

        final_state = compiled_graph.invoke(initial_state)
        return final_state

    def _display_mermaid_graph(self, mermaid_code: str):
        """
        Generates an HTML file with the Mermaid graph and opens it in a browser.
        """
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>LangGraph Workflow Diagram</title>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        // Initialize Mermaid (optional, if you want specific config or startOnLoad: false)
        // mermaid.initialize({{ startOnLoad: true }}); // Default is true
        // Force rendering if content is loaded dynamically or not on load
        document.addEventListener('DOMContentLoaded', () => {{
            mermaid.run();
        }});
    </script>
    <style>
        body {{
            font-family: sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background-color: #f4f4f4;
        }}
        .mermaid {{
            width: 90%;
            height: auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            overflow: auto; /* In case the diagram is very wide */
        }}
    </style>
</head>
<body>
    <pre class="mermaid">
{mermaid_code}
    </pre>
</body>
</html>
        """
        
        # Create a unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"langgraph_workflow_{timestamp}.html"
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, file_name)

        with open(file_path, "w") as f:
            f.write(html_content)
        
        print(f"\n--- LangGraph Workflow Diagram saved to {file_path} ---")
        webbrowser.open(f"file://{file_path}")
        print("--- Opening diagram in web browser ---")


if __name__ == "__main__":
    workflow_instance = GithubTokenVerificationWorkflow()

    # --- Test Cases ---

    # 1. Test with a valid token (replace with a real, valid token for your testing)
    valid_token = os.getenv("GITHUB_VALID_TEST_TOKEN", "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx_VALID")
    print(f"\n--- Verifying a VALID token (starts with {valid_token[:5]}...) ---")
    result_valid = workflow_instance.run(valid_token)
    print("\n--- VALID TOKEN VERIFICATION RESULT ---")
    print(f"Token valid: {result_valid['verification_result']['valid']}")
    print(f"Scopes: {result_valid['verification_result']['scopes']}")
    print(f"Analysis: {result_valid['analysis_message']}")
    print(f"Remediation: {result_valid['remediation_suggestions']}")
    print(f"Final Status Code from GitHub: {result_valid['verification_result']['status_code']}")

    # 2. Test with an invalid token
    invalid_token = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx_INVALID"
    print(f"\n--- Verifying an INVALID token (starts with {invalid_token[:5]}...) ---")
    result_invalid = workflow_instance.run(invalid_token)
    print("\n--- INVALID TOKEN VERIFICATION RESULT ---")
    print(f"Token valid: {result_invalid['verification_result']['valid']}")
    print(f"Scopes: {result_invalid['verification_result']['scopes']}")
    print(f"Analysis: {result_invalid['analysis_message']}")
    print(f"Remediation: {result_invalid['remediation_suggestions']}")
    print(f"Final Status Code from GitHub: {result_invalid['verification_result']['status_code']}")

    # 3. Test with a malformed token (shorter, clearly not a real token)
    malformed_token = "invalid_short_token"
    print(f"\n--- Verifying a MALFORMED token (starts with {malformed_token[:5]}...) ---")
    result_malformed = workflow_instance.run(malformed_token)
    print("\n--- MALFORMED TOKEN VERIFICATION RESULT ---")
    print(f"Token valid: {result_malformed['verification_result']['valid']}")
    print(f"Scopes: {result_malformed['verification_result']['scopes']}")
    print(f"Analysis: {result_malformed['analysis_message']}")
    print(f"Remediation: {result_malformed['remediation_suggestions']}")
    print(f"Final Status Code from GitHub: {result_malformed['verification_result']['status_code']}")