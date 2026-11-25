from langgraph.graph import END, StateGraph, START
from .nodes import *
from .state import AgentState

class PDFAgentBuilder:
    def __init__(self, memory_saver=None):
        self.memory_saver = memory_saver
        
    def build(self):
        workflow = StateGraph(AgentState)        
        workflow.add_node("planner", planner)
        workflow.add_node("run_querys", run_querys)
        workflow.add_node("page_grader", page_grader)
        workflow.add_node("compile_context", compile_context)
        workflow.add_node("evaluate_context", evaluate_context)
        workflow.add_node("generate_answer", generate_answer)

        workflow.set_entry_point("planner")
        workflow.add_conditional_edges("run_querys", map_pages, ["page_grader"])
        workflow.add_edge("compile_context", "evaluate_context")
        workflow.add_edge("generate_answer", END)     
        return workflow.compile(checkpointer=self.memory_saver)