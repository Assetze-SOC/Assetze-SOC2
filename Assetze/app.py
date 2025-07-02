# langgraph_app.py
from fastapi import FastAPI
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from verify import verify_github_token_tool # Import your tool
import uvicorn
import json

app = FastAPI()

# Define the state of the graph
class WorkflowState:
    token: str
    verification_result: dict
    analysis_message: str
    remediation_suggestions: str

# Define the LLM
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# Define the nodes
def call_token_verifier(state: WorkflowState):
    result_json = verify_github_token_tool.run(state.token)
    state.verification_result = json.loads(result_json)
    return state

def analyze_verification_result(state: WorkflowState):
    is_valid = state.verification_result.get("valid")
    message = state.verification_result.get("message")
    scopes = state.verification_result.get("scopes")
    status_code = state.verification_result.get("status_code")

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are an AI assistant analyzing GitHub token verification results. Summarize the outcome and state if the token is valid or invalid. If valid, list the scopes. If invalid, provide a concise reason."),
        ("human", f"Verification Result:\nValid: {is_valid}\nMessage: {message}\nScopes: {scopes}\nStatus Code: {status_code}")
    ])
    chain = prompt_template | llm
    analysis = chain.invoke({"input": ""}).content
    state.analysis_message = analysis
    return state

def generate_remediation_suggestions(state: WorkflowState):
    is_valid = state.verification_result.get("valid")
    message = state.verification_result.get("message")
    status_code = state.verification_result.get("status_code")

    if is_valid:
        state.remediation_suggestions = "Token is valid. No remediation needed."
        return state

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are an AI assistant providing remediation advice for GitHub token issues. Based on the error message, suggest concrete steps to resolve the issue."),
        ("human", f"Error Message: {message}\nStatus Code: {status_code}\nWhat steps should I take to fix this GitHub token issue?")
    ])
    chain = prompt_template | llm
    suggestions = chain.invoke({"input": ""}).content
    state.remediation_suggestions = suggestions
    return state

# Define the graph
workflow = StateGraph(WorkflowState)

workflow.add_node("verify", call_token_verifier)
workflow.add_node("analyze", analyze_verification_result)
workflow.add_node("remediate", generate_remediation_suggestions)

workflow.set_entry_point("verify")

workflow.add_edge("verify", "analyze")

def should_remediate(state: WorkflowState):
    return "remediate" if not state.verification_result.get("valid") else "end"

workflow.add_conditional_edges(
    "analyze",
    should_remediate,
    {
        "remediate": "remediate",
        "end": END
    }
)
workflow.add_edge("remediate", END)

app_graph = workflow.compile()

@app.post("/verify_token_langgraph/")
async def verify_token_langgraph_endpoint(token_data: dict):
    token = token_data.get("token")
    if not token:
        return {"error": "Token not provided"}, 400

    # Initialize state with the token
    initial_state = WorkflowState(
        token=token,
        verification_result={},
        analysis_message="",
        remediation_suggestions=""
    )

    final_state = app_graph.invoke(initial_state) # Invoke the graph

    return {
        "token_valid": final_state.verification_result.get("valid"),
        "scopes": final_state.verification_result.get("scopes"),
        "analysis": final_state.analysis_message,
        "remediation_suggestions": final_state.remediation_suggestions,
        "status_code_from_github": final_state.verification_result.get("status_code")
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)