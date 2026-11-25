from typing import Annotated, TypedDict, List, Dict
from pydantic import BaseModel, Field
from typing import Dict, TypedDict, Annotated
from operator import add
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

def docs_reducer(current_values, new_values):
    if isinstance(new_values, str) and new_values == "__CLEAR__":
        return []
    return current_values + new_values

class AgentState(TypedDict):
    """Estado do agente."""
    query: str
    context_plan: str
    concepts: List[str]
    query_history: Annotated[List[Dict], add]
    messages: Annotated[List[BaseMessage], add_messages]
    docs: Annotated[List[str], docs_reducer]
    pages: Annotated[List[Dict], docs_reducer]
    context: str
    feedback: str
    pdf_data: List[Dict]
    retry_count: int
    stage: str

class QueryGrader(BaseModel):
    """Avaliação se uma query é semelhante a uma query anterior."""
    is_relevant: bool = Field(description="Indica se as queries são semelhantes")

class PageRelevance(BaseModel):
    """Avaliação da relevância de uma página para a consulta."""
    is_relevant: bool = Field(description="Indica se a página é relevante para a consulta")
    relevance_score: int = Field(description="Pontuação de relevância de 1 a 10")
    reason: str = Field(description="Motivo pelo qual a página é ou não relevante")

class ChunkRelevance(BaseModel):
    """Avaliação da relevância se um tópico é relevante para a consulta."""
    is_relevant: bool = Field(description="Indica se o tópico é relevante para a consulta")

class PageExtraction(BaseModel):
    """Informações extraídas de uma página relevante."""
    extracted_content: str = Field(description="Conteúdo extraído da página que é relevante para a consulta e conceitos")
    extraction_quality: int = Field(description="Qualidade da extração em uma escala de 1 a 10")
    missing_information: str = Field(description="Informações que seriam úteis mas não foram encontradas na página")

class Reflexion(BaseModel):
    """Resultado da reflexão sobre a adequação do contexto para responder à consulta."""
    can_be_answered: bool = Field(description="Indica se a consulta pode ser respondida com o contexto atual")
    feedback: str = Field(description="Feedback explicando o que falta no contexto caso não possa ser respondida, ou vazio se puder ser respondida")
    missing_concepts: List[str] = Field(description="Conceitos que não foram adequadamente explorados no contexto atual")

class QueryCriteria(BaseModel):
    """Critérios de avaliação para encontrar conteúdo relevante que responda à pergunta."""
    topics: List[str] = Field(description="Tópicos ou conceitos-chave relacionados à pergunta que devem ser buscados no documento")
    evaluation_criteria: str = Field(description="Informações que o texto deve conter para ser relevante na resposta à pergunta")
    query: str = Field(description="Pergunta do usuário que o agente deve responder")