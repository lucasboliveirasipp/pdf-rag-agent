from PyPDF2 import PdfReader
from langchain_core.prompts import PromptTemplate
from typing import List, Dict, TypedDict, Annotated
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph, START
import operator
from langgraph.constants import Send
from .config import llm
from .prompts import extract_prompt

class Topic(BaseModel):
    topic_name: str = Field(description="Nome do tópico encontrado")
    topic_desc: str = Field(description="Descrição do assunto abordado no tópico encontrado")
    keywords: List[str] = Field(description="Palavras chave do tópico encontrado")
    topic_knowledge: str = Field(description="Conhecimento relevante no textosobre o tópico encontrado")

class PageMetadata(BaseModel):
    summary: str = Field(description="Resumo descritivo do conteúdo da página")
    main_topics: List[Topic] = Field(description="Principais tópicos abordados na página")
    page_type: str = Field(description="Tipos de informações encontradas na página (ex: introdução, cláusula contratual, anexo, ...)")

# class PageTopics(BaseModel):
#     metadata: PageMetadata = Field(description="Metadados descritivos sobre o conteúdo da página")

class WorkflowState(TypedDict):
    pages: List[str]
    topics: Annotated[List[Dict], operator.add]
    pdf_data: List[Dict]

class DocumentProcessor:
    def __init__(self, pdf_docs):
        self.pdf_docs = pdf_docs
        self.llm = llm
        self.workflow = self._setup_workflow()
        
    def _setup_workflow(self):
        extract_template = PromptTemplate(
            template=extract_prompt,
            input_variables=["page"]
        )
        
        #llm_metadata = self.llm.with_structured_output(PageTopics)
        llm_metadata = self.llm.with_structured_output(PageMetadata)
        
        self.extract_chain = extract_template | llm_metadata

        workflow = StateGraph(WorkflowState)
        workflow.add_node("extraction_node", self.extract_topics)
        workflow.add_node("map_topics", self.map_node)
        workflow.add_node("reduce_topics", self.reducer_node)
        workflow.add_conditional_edges(START, self.map_node, ["extraction_node"])
        workflow.add_edge("extraction_node", "reduce_topics")
        workflow.add_edge("reduce_topics", END)
        
        return workflow.compile()
    
    def extract_topics(self, state: WorkflowState):
        page = state["pages"]

        result = self.extract_chain.invoke(page)
        topics = result.model_dump()
        topics["page_text"] = page
        result = {"metadata": topics}
        return {"topics": [result]}
        #return {"topics": [topics]}
    
    def map_node(self, state: WorkflowState):
        return [Send("extraction_node", {"pages": p}) for p in state["pages"]]
    
    def reducer_node(self, state: WorkflowState):
        pages_list = []
        
        for page_index, page_topics in enumerate(state["topics"]):
            page_number = page_index + 1

            page_metadata = page_topics.get("metadata", {})
            raw_text = page_topics.get("page_text", "")

            page_dict = {
                "page_number": page_number,
                "metadata": page_metadata,
                "raw_text": raw_text
            }
            
            pages_list.append(page_dict)
        
        return {"pdf_data": pages_list}
    
    def extract_text_from_pdf(self, file):
        if hasattr(file, 'read') and hasattr(file, 'seek'):
            file.seek(0)
            reader = PdfReader(file)
        else:
            reader = PdfReader(file)
            
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text())
        return pages
    
    def process_documents(self) -> List[Dict]:
        all_pages = []
        for pdf in self.pdf_docs:
            pages = self.extract_text_from_pdf(pdf)
            all_pages.extend(pages)
            
        result = self.workflow.invoke({"pages": all_pages})
        return result["pdf_data"]

def save_to_json(data, output_file):
    import json
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    file = 'teste.pdf'
    document_processor = DocumentProcessor([file])
    result = document_processor.process_documents()

    output_file = 'resultado_processamento.json'
    save_to_json(result, output_file)
    print(f"Resultado salvo em: {output_file}")
    print(result)