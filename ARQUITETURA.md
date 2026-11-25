# Arquitetura do Agente PDF RAG

## Visão Geral

Este documento explica a arquitetura do sistema de RAG (Retrieval-Augmented Generation) para processamento de PDFs, focando em como os documentos são processados, como funciona a busca e como adaptar para indexação em Azure com múltiplos PDFs.

## Arquitetura Atual

### 1. Componentes Principais

#### 1.1 `config.py` - Configuração do Azure OpenAI
```python
# Configuração do Azure OpenAI
- AzureChatOpenAI: LLM para geração de respostas
- AzureOpenAIEmbeddings: Modelo de embeddings (text-embedding-ada-002)
- Endpoints Azure
```

**Observação Importante**: O sistema atual **NÃO utiliza Azure AI Search** ou qualquer serviço de indexação persistente. Os documentos são processados e armazenados apenas em memória durante a sessão.

#### 1.2 `document_process.py` - Processamento de Documentos

**Fluxo de Processamento:**

1. **Extração de Texto**: Usa `PyPDF2` para extrair texto de cada página do PDF
2. **Workflow LangGraph**: Processa páginas em paralelo usando um grafo de estado
3. **Extração de Metadados**: Para cada página, extrai:
   - Resumo descritivo
   - Tópicos principais
   - Palavras-chave
   - Tipo de página
   - Conhecimento relevante

**Estrutura de Dados Gerada:**
```python
{
    "page_number": int,
    "metadata": {
        "summary": str,
        "main_topics": [Topic],
        "page_type": str
    },
    "raw_text": str
}
```

#### 1.3 `graph_builder.py` - Construção do Grafo do Agente

O agente usa um grafo de estados com os seguintes nós:
- `planner`: Planeja a busca baseado na query
- `run_querys`: Nó vazio (não implementado - seria para busca vetorial)
- `page_grader`: Avalia relevância de cada página
- `compile_context`: Compila contexto das páginas relevantes
- `evaluate_context`: Avalia se o contexto é suficiente
- `generate_answer`: Gera resposta final

#### 1.4 `nodes.py` - Lógica dos Nós

**Planner**: 
- Analisa a query do usuário
- Identifica conceitos-chave e critérios de busca
- Verifica histórico de queries similares (cache)
- Pode fazer retry com feedback

**Page Grader**:
- Avalia relevância de cada página usando LLM
- Extrai conteúdo relevante das páginas selecionadas
- Usa metadados para filtragem inicial

**Busca Atual**: 
- **NÃO usa busca vetorial** (embeddings não são utilizados)
- Busca baseada em avaliação LLM de relevância
- Processa todas as páginas sequencialmente

### 2. Limitações da Arquitetura Atual

1. **Sem Indexação Persistente**: Documentos são processados apenas em memória
2. **Sem Busca Vetorial**: Embeddings são configurados mas não utilizados
3. **Processamento Sequencial**: Todas as páginas são avaliadas para cada query
4. **Sem Suporte a Múltiplos PDFs**: Processa um PDF por vez
5. **Sem Limpeza de Índice**: Não há mecanismo de limpeza

## Arquitetura Proposta para Indexação em Azure

### 1. Componentes Necessários

#### 1.1 Azure AI Search (Azure Cognitive Search)

**Por que usar:**
- Indexação persistente de documentos
- Busca vetorial híbrida (semântica + texto)
- Suporte a múltiplos documentos
- Escalabilidade e performance
- APIs de gerenciamento de índice

#### 1.2 Estrutura de Índice Proposta

```python
# Schema do índice Azure AI Search
{
    "id": "unique_document_id",  # ID único do documento
    "document_name": str,         # Nome do arquivo PDF
    "page_number": int,           # Número da página
    "content": str,               # Texto completo da página
    "content_vector": List[float], # Embedding vetorial
    "metadata_summary": str,       # Resumo da página
    "main_topics": List[str],      # Tópicos principais
    "keywords": List[str],         # Palavras-chave
    "page_type": str,              # Tipo de página
    "upload_timestamp": datetime,  # Data de upload
    "document_group": str          # Grupo/categoria do documento
}
```

### 2. Fluxo de Indexação de Múltiplos PDFs

#### 2.1 Processo de Indexação

```python
class AzureIndexer:
    def __init__(self, search_client, embeddings):
        self.search_client = search_client
        self.embeddings = embeddings
    
    def index_multiple_pdfs(self, pdf_files: List[File]):
        """
        Indexa múltiplos PDFs de uma vez
        """
        all_documents = []
        
        for pdf_file in pdf_files:
            # 1. Processar PDF (extrair texto e metadados)
            processor = DocumentProcessor([pdf_file])
            pdf_data = processor.process_documents()
            
            # 2. Gerar embeddings para cada página
            for page_data in pdf_data:
                # Gerar embedding do texto
                embedding = self.embeddings.embed_query(page_data["raw_text"])
                
                # Criar documento para índice
                doc = {
                    "id": f"{pdf_file.name}_{page_data['page_number']}",
                    "document_name": pdf_file.name,
                    "page_number": page_data["page_number"],
                    "content": page_data["raw_text"],
                    "content_vector": embedding,
                    "metadata_summary": page_data["metadata"]["summary"],
                    "main_topics": [t["topic_name"] for t in page_data["metadata"]["main_topics"]],
                    "keywords": self._extract_keywords(page_data["metadata"]),
                    "page_type": page_data["metadata"]["page_type"],
                    "upload_timestamp": datetime.now().isoformat(),
                    "document_group": self._get_document_group(pdf_file)
                }
                all_documents.append(doc)
        
        # 3. Upload em batch para Azure AI Search
        self.search_client.upload_documents(documents=all_documents)
        
        return len(all_documents)
```

#### 2.2 Processamento em Lote (Batch)

```python
def index_pdfs_batch(self, pdf_files: List[File], batch_size: int = 100):
    """
    Indexa PDFs em lotes para melhor performance
    """
    total_indexed = 0
    
    for i in range(0, len(pdf_files), batch_size):
        batch = pdf_files[i:i + batch_size]
        indexed = self.index_multiple_pdfs(batch)
        total_indexed += indexed
        
        # Log de progresso
        print(f"Indexados {total_indexed} documentos até agora...")
    
    return total_indexed
```

### 3. Busca Vetorial com Azure AI Search

#### 3.1 Modificação do Nó `run_querys`

```python
def run_querys(state: AgentState):
    """
    Busca documentos relevantes usando Azure AI Search
    """
    query = state.get("query", "")
    concepts = state.get("concepts", [])
    
    # 1. Gerar embedding da query
    query_embedding = embeddings.embed_query(query)
    
    # 2. Construir busca híbrida
    search_options = {
        "vector": {
            "value": query_embedding,
            "k_nearest_neighbors": 10,
            "fields": "content_vector"
        },
        "search": query,  # Busca textual também
        "select": ["id", "content", "metadata_summary", "main_topics", 
                   "page_number", "document_name"],
        "top": 10
    }
    
    # 3. Executar busca
    results = search_client.search(
        search_text=query,
        vector_queries=[{
            "vector": query_embedding,
            "k_nearest_neighbors": 10,
            "fields": "content_vector"
        }],
        top=10
    )
    
    # 4. Formatar resultados no formato esperado
    pdf_data = []
    for result in results:
        pdf_data.append({
            "page_number": result["page_number"],
            "metadata": {
                "summary": result["metadata_summary"],
                "main_topics": result["main_topics"]
            },
            "raw_text": result["content"],
            "document_name": result["document_name"],
            "relevance_score": result["@search.score"]
        })
    
    return {"pdf_data": pdf_data}
```

### 4. Limpeza do Índice

#### 4.1 Estratégias de Limpeza

**Opção 1: Limpeza por Documento**
```python
def delete_document_from_index(self, document_name: str):
    """
    Remove todas as páginas de um documento específico
    """
    # Buscar todos os documentos com esse nome
    search_results = self.search_client.search(
        search_text="*",
        filter=f"document_name eq '{document_name}'",
        select=["id"]
    )
    
    # Deletar documentos
    ids_to_delete = [{"id": doc["id"]} for doc in search_results]
    if ids_to_delete:
        self.search_client.delete_documents(documents=ids_to_delete)
    
    return len(ids_to_delete)
```

**Opção 2: Limpeza por Grupo/Categoria**
```python
def delete_document_group(self, document_group: str):
    """
    Remove todos os documentos de um grupo específico
    """
    search_results = self.search_client.search(
        search_text="*",
        filter=f"document_group eq '{document_group}'",
        select=["id"]
    )
    
    ids_to_delete = [{"id": doc["id"]} for doc in search_results]
    if ids_to_delete:
        self.search_client.delete_documents(documents=ids_to_delete)
    
    return len(ids_to_delete)
```

**Opção 3: Limpeza por Data**
```python
def delete_old_documents(self, days_old: int = 30):
    """
    Remove documentos mais antigos que X dias
    """
    cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
    
    search_results = self.search_client.search(
        search_text="*",
        filter=f"upload_timestamp lt '{cutoff_date}'",
        select=["id"]
    )
    
    ids_to_delete = [{"id": doc["id"]} for doc in search_results]
    if ids_to_delete:
        self.search_client.delete_documents(documents=ids_to_delete)
    
    return len(ids_to_delete)
```

**Opção 4: Limpeza Completa do Índice**
```python
def clear_index(self):
    """
    Remove TODOS os documentos do índice
    """
    # Buscar todos os documentos
    search_results = self.search_client.search(
        search_text="*",
        select=["id"]
    )
    
    ids_to_delete = [{"id": doc["id"]} for doc in search_results]
    if ids_to_delete:
        self.search_client.delete_documents(documents=ids_to_delete)
    
    return len(ids_to_delete)
```

### 5. Implementação Completa Sugerida

#### 5.1 Novo Arquivo: `azure_indexer.py`

```python
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from datetime import datetime, timedelta
from typing import List, Dict
from .document_process import DocumentProcessor
from .config import embeddings

class AzureIndexer:
    def __init__(self, endpoint: str, index_name: str, api_key: str):
        credential = AzureKeyCredential(api_key)
        self.search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=credential
        )
        self.embeddings = embeddings
    
    def index_multiple_pdfs(self, pdf_files: List, document_group: str = "default"):
        """Indexa múltiplos PDFs"""
        all_documents = []
        
        for pdf_file in pdf_files:
            processor = DocumentProcessor([pdf_file])
            pdf_data = processor.process_documents()
            
            for page_data in pdf_data:
                embedding = self.embeddings.embed_query(page_data["raw_text"])
                
                doc = {
                    "id": f"{pdf_file.name}_{page_data['page_number']}_{datetime.now().timestamp()}",
                    "document_name": pdf_file.name,
                    "page_number": page_data["page_number"],
                    "content": page_data["raw_text"],
                    "content_vector": embedding,
                    "metadata_summary": page_data["metadata"]["summary"],
                    "main_topics": [t["topic_name"] for t in page_data["metadata"]["main_topics"]],
                    "keywords": self._extract_keywords(page_data["metadata"]),
                    "page_type": page_data["metadata"]["page_type"],
                    "upload_timestamp": datetime.now().isoformat(),
                    "document_group": document_group
                }
                all_documents.append(doc)
        
        # Upload em batch
        result = self.search_client.upload_documents(documents=all_documents)
        return len(all_documents)
    
    def delete_document(self, document_name: str):
        """Remove um documento específico"""
        # Implementação da limpeza por documento
        pass
    
    def clear_index(self):
        """Limpa todo o índice"""
        # Implementação da limpeza completa
        pass
```

#### 5.2 Modificação em `config.py`

```python
# Adicionar configurações do Azure AI Search
os.environ['AZURE_SEARCH_ENDPOINT'] = 'https://seu-recurso.search.windows.net'
os.environ['AZURE_SEARCH_INDEX_NAME'] = 'pdf-documents-index'
os.environ['AZURE_SEARCH_API_KEY'] = 'your-api-key'
```

#### 5.3 Modificação em `nodes.py`

```python
from .azure_indexer import AzureIndexer
from .config import search_client, embeddings

def run_querys(state: AgentState):
    """Busca usando Azure AI Search"""
    # Implementação da busca vetorial
    pass
```

## Resumo da Arquitetura

### Arquitetura Atual
- ✅ Processamento de PDFs com extração de metadados
- ✅ Avaliação de relevância usando LLM
- ❌ Sem indexação persistente
- ❌ Sem busca vetorial
- ❌ Processamento sequencial lento

### Arquitetura Proposta
- ✅ Processamento de PDFs com extração de metadados
- ✅ Indexação persistente no Azure AI Search
- ✅ Busca vetorial híbrida (semântica + texto)
- ✅ Suporte a múltiplos PDFs em batch
- ✅ Limpeza de índice por documento/grupo/data
- ✅ Performance melhorada com busca vetorial

## Próximos Passos para Implementação

1. **Criar serviço Azure AI Search** no portal Azure
2. **Definir schema do índice** com campos vetoriais
3. **Implementar `azure_indexer.py`** com métodos de indexação e limpeza
4. **Modificar `nodes.py`** para usar busca vetorial
5. **Atualizar `agent.py`** para suportar múltiplos PDFs
6. **Adicionar interface** para gerenciamento de índice (upload/limpeza)

