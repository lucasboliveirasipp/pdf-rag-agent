# Guia de Configuração do Azure AI Search para Indexação de PDFs

## Pré-requisitos

1. Conta Azure ativa
2. Acesso ao portal Azure
3. Python 3.8+ instalado
4. Bibliotecas necessárias instaladas

## Passo 1: Criar Serviço Azure AI Search

### 1.1 No Portal Azure

1. Acesse o [Portal Azure](https://portal.azure.com)
2. Clique em "Criar um recurso"
3. Busque por "Azure AI Search" ou "Azure Cognitive Search"
4. Clique em "Criar"

### 1.2 Configurações Recomendadas

- **Assinatura**: Sua assinatura Azure
- **Grupo de recursos**: Crie um novo ou use existente
- **Nome do serviço**: `pdf-search-service` (ou outro nome único)
- **Localização**: Escolha a região mais próxima
- **Tipo de preço**: 
  - **Básico**: Para desenvolvimento/testes (até 2GB)
  - **Standard**: Para produção (escalável)
- **Réplicas**: 1 (pode aumentar para produção)
- **Partições**: 1 (pode aumentar para produção)

### 1.3 Obter Credenciais

Após criar o serviço:

1. Vá para "Chaves" no menu lateral
2. Copie:
   - **URL do serviço**: `https://seu-recurso.search.windows.net`
   - **Chave de administração primária**: (use esta para indexação)

## Passo 2: Criar Índice no Azure AI Search

### 2.1 Schema do Índice

O índice precisa ter os seguintes campos:

```json
{
  "name": "pdf-documents-index",
  "fields": [
    {
      "name": "id",
      "type": "Edm.String",
      "key": true,
      "searchable": false,
      "filterable": true,
      "sortable": false,
      "facetable": false
    },
    {
      "name": "document_name",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true,
      "sortable": true,
      "facetable": true
    },
    {
      "name": "page_number",
      "type": "Edm.Int32",
      "searchable": false,
      "filterable": true,
      "sortable": true,
      "facetable": true
    },
    {
      "name": "content",
      "type": "Edm.String",
      "searchable": true,
      "filterable": false,
      "sortable": false,
      "facetable": false,
      "analyzer": "pt-BR.lucene"
    },
    {
      "name": "content_vector",
      "type": "Collection(Edm.Single)",
      "searchable": false,
      "filterable": false,
      "sortable": false,
      "facetable": false,
      "dimensions": 1536,
      "vectorSearchProfile": "vector-profile"
    },
    {
      "name": "metadata_summary",
      "type": "Edm.String",
      "searchable": true,
      "filterable": false,
      "sortable": false,
      "facetable": false
    },
    {
      "name": "main_topics",
      "type": "Collection(Edm.String)",
      "searchable": true,
      "filterable": true,
      "sortable": false,
      "facetable": true
    },
    {
      "name": "keywords",
      "type": "Collection(Edm.String)",
      "searchable": true,
      "filterable": true,
      "sortable": false,
      "facetable": true
    },
    {
      "name": "page_type",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "sortable": false,
      "facetable": true
    },
    {
      "name": "upload_timestamp",
      "type": "Edm.DateTimeOffset",
      "searchable": false,
      "filterable": true,
      "sortable": true,
      "facetable": false
    },
    {
      "name": "document_group",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "sortable": false,
      "facetable": true
    }
  ],
  "vectorSearch": {
    "algorithms": [
      {
        "name": "hnsw-config",
        "kind": "hnsw",
        "hnswParameters": {
          "metric": "cosine",
          "m": 4,
          "efConstruction": 400,
          "efSearch": 500
        }
      }
    ],
    "profiles": [
      {
        "name": "vector-profile",
        "algorithm": "hnsw-config"
      }
    ]
  }
}
```

### 2.2 Criar Índice via Portal Azure

1. No seu serviço Azure AI Search, vá para "Índices"
2. Clique em "Criar índice"
3. Cole o JSON acima ou use o editor visual
4. Clique em "Criar"

### 2.3 Criar Índice via Python (Alternativa)

```python
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchAlgorithmKind,
    VectorSearchProfile,
    VectorSearchAlgorithmMetric
)
from azure.core.credentials import AzureKeyCredential

def create_index(search_endpoint: str, api_key: str, index_name: str):
    credential = AzureKeyCredential(api_key)
    index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)
    
    # Definir campos
    fields = [
        SimpleField(name="id", type="Edm.String", key=True),
        SearchableField(name="document_name", type="Edm.String", filterable=True, sortable=True, facetable=True),
        SimpleField(name="page_number", type="Edm.Int32", filterable=True, sortable=True, facetable=True),
        SearchableField(name="content", type="Edm.String", analyzer_name="pt-BR.lucene"),
        SimpleField(name="content_vector", type="Collection(Edm.Single)", 
                   vector_search_dimensions=1536, vector_search_profile="vector-profile"),
        SearchableField(name="metadata_summary", type="Edm.String"),
        SearchableField(name="main_topics", type="Collection(Edm.String)", filterable=True, facetable=True),
        SearchableField(name="keywords", type="Collection(Edm.String)", filterable=True, facetable=True),
        SimpleField(name="page_type", type="Edm.String", filterable=True, facetable=True),
        SimpleField(name="upload_timestamp", type="Edm.DateTimeOffset", filterable=True, sortable=True),
        SimpleField(name="document_group", type="Edm.String", filterable=True, facetable=True)
    ]
    
    # Configurar busca vetorial
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw-config",
                kind=VectorSearchAlgorithmKind.HNSW,
                parameters={
                    "metric": VectorSearchAlgorithmMetric.COSINE,
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500
                }
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm="hnsw-config"
            )
        ]
    )
    
    # Criar índice
    index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)
    index_client.create_index(index)
    print(f"Índice '{index_name}' criado com sucesso!")

# Uso
create_index(
    search_endpoint="https://seu-recurso.search.windows.net",
    api_key="sua-chave-api",
    index_name="pdf-documents-index"
)
```

## Passo 3: Instalar Dependências Python

```bash
pip install azure-search-documents
pip install azure-identity
pip install langchain-openai
pip install PyPDF2
```

## Passo 4: Configurar Variáveis de Ambiente

Crie um arquivo `.env` ou configure variáveis de ambiente:

```bash
# Azure OpenAI (já configurado)
AZURE_OPENAI_ENDPOINT=https://seu-recurso.openai.azure.com/
AZURE_OPENAI_API_KEY=sua-chave-openai
OPENAI_API_TYPE=azure
API_VERSION=2024-08-01-preview
GPT4=gpt-4o-mini

# Azure AI Search (novo)
AZURE_SEARCH_ENDPOINT=https://seu-recurso.search.windows.net
AZURE_SEARCH_INDEX_NAME=pdf-documents-index
AZURE_SEARCH_API_KEY=sua-chave-search
```

Ou atualize `config.py`:

```python
# Adicionar ao config.py
os.environ['AZURE_SEARCH_ENDPOINT'] = 'https://seu-recurso.search.windows.net'
os.environ['AZURE_SEARCH_INDEX_NAME'] = 'pdf-documents-index'
os.environ['AZURE_SEARCH_API_KEY'] = 'sua-chave-search'
```

## Passo 5: Testar a Implementação

### 5.1 Teste de Indexação

```python
from exemplo_implementacao import AzurePDFIndexer
import os

# Inicializar
indexer = AzurePDFIndexer(
    search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
    api_key=os.getenv("AZURE_SEARCH_API_KEY")
)

# Indexar PDFs
pdf_files = ["documento1.pdf", "documento2.pdf"]
resultado = indexer.index_multiple_pdfs(
    pdf_files=pdf_files,
    document_group="teste",
    batch_size=50
)

print(f"Indexados: {resultado['successful']} documentos")
```

### 5.2 Teste de Busca

```python
# Buscar documentos
resultados = indexer.search_documents(
    query="termos do contrato",
    top=5
)

for doc in resultados:
    print(f"Documento: {doc['document_name']}, Página: {doc['page_number']}")
    print(f"Score: {doc['relevance_score']}")
    print(f"Conteúdo: {doc['content'][:200]}...")
    print("---")
```

### 5.3 Teste de Limpeza

```python
# Remover documento específico
removidos = indexer.delete_document("documento1.pdf")
print(f"Removidos {removidos} documentos")

# Obter estatísticas
stats = indexer.get_index_stats()
print(f"Total de documentos no índice: {stats['total_documents']}")
```

## Passo 6: Integrar com o Agente Existente

### 6.1 Modificar `nodes.py`

Substituir a função `run_querys`:

```python
from exemplo_implementacao import AzurePDFIndexer
import os

# Inicializar indexador (fazer uma vez, pode ser global ou singleton)
_indexer = None

def get_indexer():
    global _indexer
    if _indexer is None:
        _indexer = AzurePDFIndexer(
            search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
            api_key=os.getenv("AZURE_SEARCH_API_KEY")
        )
    return _indexer

def run_querys(state: AgentState):
    """Busca documentos usando Azure AI Search"""
    query = state.get("query", "")
    concepts = state.get("concepts", [])
    
    indexer = get_indexer()
    
    # Buscar documentos relevantes
    search_results = indexer.search_documents(
        query=query,
        top=10
    )
    
    # Converter para formato esperado pelo agente
    pdf_data = []
    for result in search_results:
        pdf_data.append({
            "page_number": result["page_number"],
            "metadata": {
                "summary": result["metadata_summary"],
                "main_topics": result["main_topics"]
            },
            "raw_text": result["content"],
            "document_name": result["document_name"],
            "relevance_score": result["relevance_score"]
        })
    
    return {"pdf_data": pdf_data}
```

### 6.2 Modificar `agent.py` para Suportar Múltiplos PDFs

```python
# No formulário, permitir múltiplos arquivos
uploaded_files = st.file_uploader(
    "Carregar PDFs", 
    type=['pdf'], 
    accept_multiple_files=True  # Mudança aqui
)

if st.form_submit_button("Indexar PDFs") and uploaded_files:
    try:
        from exemplo_implementacao import AzurePDFIndexer
        
        indexer = AzurePDFIndexer(
            search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
            api_key=os.getenv("AZURE_SEARCH_API_KEY")
        )
        
        # Indexar múltiplos PDFs
        resultado = indexer.index_multiple_pdfs(
            pdf_files=uploaded_files,
            document_group="chat_session",
            batch_size=100
        )
        
        st.success(f"Indexados {resultado['successful']} documentos com sucesso!")
        st.session_state["step"] = "chat"
        
    except Exception as e:
        st.error(f"Erro ao indexar documentos: {str(e)}")
```

## Custos e Limites

### Custos Azure AI Search

- **Básico**: ~$75/mês (até 2GB, 1 réplica)
- **Standard S1**: ~$250/mês (25GB, 1 réplica)
- **Standard S2**: ~$500/mês (100GB, 1 réplica)

### Limites

- **Documentos por índice**: Depende do tier
- **Tamanho máximo do documento**: 16MB
- **Dimensões do vetor**: Máximo 2048 (usamos 1536 para ada-002)
- **Taxa de indexação**: Depende do tier

## Troubleshooting

### Erro: "Index not found"
- Verifique se o índice foi criado corretamente
- Confirme o nome do índice nas variáveis de ambiente

### Erro: "Invalid API key"
- Verifique se está usando a chave de administração (não a chave de query)
- Confirme que a chave está correta

### Erro: "Vector dimensions mismatch"
- Verifique se o campo `content_vector` tem `dimensions: 1536`
- Confirme que os embeddings estão sendo gerados com o modelo correto

### Performance lenta
- Aumente o número de réplicas para melhor throughput
- Use batch_size maior na indexação
- Considere usar Standard tier para produção

## Próximos Passos

1. Implementar cache de queries similares
2. Adicionar métricas de qualidade de busca
3. Implementar reindexação incremental
4. Adicionar monitoramento e alertas
5. Otimizar para grandes volumes de documentos

