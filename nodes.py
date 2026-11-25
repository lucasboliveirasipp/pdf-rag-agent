from langchain_core.prompts import PromptTemplate
from langgraph.constants import Send
from typing import Literal
from langchain_core.prompts import PromptTemplate
from langgraph.types import Command
from .state import *
from .prompts import *
from .config import *

def planner(state: AgentState) -> Command[Literal["run_querys", "compile_context", "generate_answer"]]:  
    messages = state.get("messages", [])
    feedback = state.get("feedback", "")
    query_history = state.get("query_history", [])
    retry_count = state.get("retry_count", 0)
    stage = state.get("stage", "initial") 
    
    MAX_RETRIES = 1
    
    last_message = messages[-1].content

    if stage != "processing_similar_query":
        if query_history:            
            similarity_template = PromptTemplate(template=similarity_prompt, input_variables=["original_query", "new_query"])
            similarity_chain = similarity_template | llm.with_structured_output(QueryGrader)

            for entry in query_history:
                previous_query = entry.get("query", "")

                grade = similarity_chain.invoke({
                    "original_query": previous_query,
                    "new_query": last_message
                })

                if grade.is_relevant:
                    return Command(
                        update={
                            "docs": entry.get("context", []),
                            "query": last_message,
                            "stage": "processing_similar_query"
                        },
                        goto="compile_context"
                    )

    if feedback:
        if retry_count < MAX_RETRIES:           
            planner_prompt_template = PromptTemplate(template=planner_prompt, input_variables=["query", "feedback"])
            planner_chain = planner_prompt_template | llm.with_structured_output(QueryCriteria)
            
            query_criteria = planner_chain.invoke({"query": last_message, "feedback": feedback}).model_dump()

            return Command(
                update={
                    "context_plan": query_criteria["evaluation_criteria"],
                    "query": query_criteria["query"],
                    "concepts": query_criteria["topics"],
                    "retry_count": retry_count + 1,
                    "docs": "__CLEAR__",  
                    "pages": "__CLEAR__"  
                },
                goto="run_querys"
            )
        else:          
            return Command(
                update={
                    "context": "Após múltiplas tentativas, não foram encontrados dados suficientes no documento para responder à pergunta de forma adequada.",
                    "query": last_message,
                    "docs": [] 
                },
                goto="generate_answer"
            )
      
    planner_prompt_template = PromptTemplate(template=base_prompt, input_variables=["query"])
    planner_chain = planner_prompt_template | llm.with_structured_output(QueryCriteria)
    
    query_criteria = planner_chain.invoke({"query": last_message}).model_dump()

    return Command(
        update={
            "context_plan": query_criteria["evaluation_criteria"],
            "query": query_criteria["query"],
            "concepts": query_criteria["topics"],
            "retry_count": 0 
        },
        goto="run_querys"
    )

def run_querys(state: AgentState):
    pass

def map_pages(state: AgentState):
    pdf_data = state.get("pdf_data", [])
    concepts = state.get("concepts", [])
    criteria = state.get("context_plan", "")
    query = state.get("query", "")
    return [Send("page_grader", {"check_page": p, "concepts": concepts, "criteria": criteria, "query": query}) for p in pdf_data]

def page_grader(state: AgentState) -> Command[Literal["compile_context"]]:
    query = state.get("query", "")
    concepts = state.get("concepts", [])
    page = state.get("check_page", "")
    criteria = state.get("criteria", "")

    page_metadata = page.get('metadata', {}) if isinstance(page, dict) else {}
    page_raw_text = page.get('raw_text', '') if isinstance(page, dict) else ''
    page_number = page.get('page_number', 0) if isinstance(page, dict) else 0

    concepts_text = ", ".join(concepts) if concepts else ""
    evaluation_context = f"Query: {query}\nConceitos relacionados: {concepts_text}\nCritérios de avaliação: {criteria}"

    evaluate_page_template = PromptTemplate(
        template=evaluate_prompt_page,
        input_variables=["evaluation_context", "page_metadata"]
    )

    grade_page_chain = evaluate_page_template | llm.with_structured_output(PageRelevance)
    
    page_grade = grade_page_chain.invoke({
        "evaluation_context": evaluation_context, 
        "page_metadata": page_metadata
    })

    if page_grade.is_relevant:
        extract_info_template = PromptTemplate(
            template=extract_info_prompt,
            input_variables=["evaluation_context", "page_raw_text", "page_number"]
        )
        
        extract_info_chain = extract_info_template | llm.with_structured_output(PageExtraction)
        
        extracted_info = extract_info_chain.invoke({
            "evaluation_context": evaluation_context,
            "page_raw_text": page_raw_text,
            "page_number": page_number
        })
        

        if extracted_info.extracted_content:
            return Command(
                update={"docs": [extracted_info.extracted_content]},
                goto="compile_context",
            )

    return Command(
        goto="compile_context"
    )   

def compile_context(state: AgentState):
    docs = state.get("docs", [])

    if not docs:
        return {"context": "Não foram encontrados trechos relevantes no documento para responder à pergunta."}
    
    formatted_chunks = []
    
    for i, text in enumerate(docs, 1):
        formatted_chunk = f"### Trecho {i} ###\n{text}"
        formatted_chunks.append(formatted_chunk)
    
    compiled_context = "\n\n".join(formatted_chunks)
    
    return {"context": compiled_context}

def evaluate_context(state: AgentState) -> Command[Literal["planner", "generate_answer"]]:
    reflexion_prompt_template = PromptTemplate(
        template=reflexion_prompt,
        input_variables=["query", "context", "concepts"]
    )   

    reflexion_chain = reflexion_prompt_template | llm.with_structured_output(Reflexion)

    concepts = state.get("concepts", [])
    concepts_text = ", ".join(concepts) if concepts else ""

    reflexion = reflexion_chain.invoke({
        "query": state["query"], 
        "context": state["context"],
        "concepts": concepts_text
    })

    if reflexion.can_be_answered:
        return Command(goto="generate_answer")
    
    else:
        return Command(update={"feedback": reflexion.feedback, 
                               "docs": "__CLEAR__", 
                               "pages": "__CLEAR__", 
                               "context": ""}, goto="planner")

def generate_answer(state: AgentState):
    docs = state.get("docs", [])
    mensagens = state.get("messages", [])
    query = state.get("query", "")
    concepts = state.get("concepts", [])
    concepts_text = ", ".join(concepts) if concepts else ""

    answer_chain = (
        PromptTemplate(
            input_variables=["question", "context", "messages", "concepts"],
            template=generate_answer_message
        )
        | llm
    )
    
    result = answer_chain.invoke({
        "question": query,
        "context": docs,
        "messages": mensagens,
        "concepts": concepts_text
    })

    response_tracking = {
        "query": query,
        "context": docs,
        "concepts": concepts,
        "answer": result
    }

    return {"messages": result, 
            "docs": "__CLEAR__", 
            "pages": "__CLEAR__", 
            "feedback": "", 
            "query": "", 
            "query_history": [response_tracking],
            "context": "",
            "context_plan": {},
            "concepts": [],
            "retry_count": 0,
            "stage": "initial"}