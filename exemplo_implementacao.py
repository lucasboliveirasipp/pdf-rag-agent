"""
Exemplo prático de implementação de indexação de múltiplos PDFs no Azure AI Search
e limpeza do índice. Este código pode ser adaptado para outros projetos.
"""

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
from document_process import DocumentProcessor
from config import embeddings


class AzurePDFIndexer:
    """
    Classe para indexação e gerenciamento de PDFs no Azure AI Search.
    
    Funcionalidades:
    - Indexação de múltiplos PDFs de uma vez
    - Busca vetorial híbrida
    - Limpeza de índice por documento, grupo ou data
    - Limpeza completa do índice
    """
    
    def __init__(self, 
                 search_endpoint: str,
                 index_name: str,
                 api_key: str):
        """
        Inicializa o indexador Azure.
        
        Args:
            search_endpoint: URL do serviço Azure AI Search
            index_name: Nome do índice onde os documentos serão armazenados
            api_key: Chave de API do Azure AI Search
        """
        credential = AzureKeyCredential(api_key)
        self.search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=credential
        )
        self.embeddings = embeddings
        self.index_name = index_name
    
    def _extract_keywords(self, metadata: Dict) -> List[str]:
        """
        Extrai palavras-chave dos metadados da página.
        """
        keywords = []
        if "main_topics" in metadata:
            for topic in metadata["main_topics"]:
                if "keywords" in topic:
                    keywords.extend(topic["keywords"])
        return list(set(keywords))  # Remove duplicatas
    
    def _generate_document_id(self, document_name: str, page_number: int) -> str:
        """
        Gera um ID único para cada documento/página.
        """
        timestamp = datetime.now().timestamp()
        safe_name = document_name.replace(" ", "_").replace(".", "_")
        return f"{safe_name}_page_{page_number}_{int(timestamp)}"
    
    def index_multiple_pdfs(self, 
                           pdf_files: List, 
                           document_group: str = "default",
                           batch_size: int = 100) -> Dict:
        """
        Indexa múltiplos PDFs de uma vez no Azure AI Search.
        
        Args:
            pdf_files: Lista de arquivos PDF para indexar
            document_group: Grupo/categoria dos documentos (útil para organização)
            batch_size: Tamanho do lote para upload (padrão: 100)
        
        Returns:
            Dict com estatísticas da indexação:
            {
                "total_documents": int,
                "total_pages": int,
                "successful": int,
                "failed": int,
                "document_names": List[str]
            }
        """
        all_documents = []
        document_names = []
        total_pages = 0
        
        print(f"Iniciando indexação de {len(pdf_files)} PDF(s)...")
        
        # Processar cada PDF
        for pdf_file in pdf_files:
            try:
                # Obter nome do arquivo
                file_name = pdf_file.name if hasattr(pdf_file, 'name') else str(pdf_file)
                document_names.append(file_name)
                
                print(f"Processando: {file_name}")
                
                # Processar PDF (extrair texto e metadados)
                processor = DocumentProcessor([pdf_file])
                pdf_data = processor.process_documents()
                
                # Processar cada página
                for page_data in pdf_data:
                    try:
                        # Gerar embedding do texto da página
                        embedding = self.embeddings.embed_query(page_data["raw_text"])
                        
                        # Extrair tópicos
                        main_topics = []
                        if "main_topics" in page_data.get("metadata", {}):
                            for topic in page_data["metadata"]["main_topics"]:
                                if isinstance(topic, dict):
                                    main_topics.append(topic.get("topic_name", ""))
                                elif hasattr(topic, "topic_name"):
                                    main_topics.append(topic.topic_name)
                        
                        # Criar documento para o índice
                        doc = {
                            "id": self._generate_document_id(file_name, page_data["page_number"]),
                            "document_name": file_name,
                            "page_number": page_data["page_number"],
                            "content": page_data["raw_text"],
                            "content_vector": embedding,
                            "metadata_summary": page_data.get("metadata", {}).get("summary", ""),
                            "main_topics": main_topics,
                            "keywords": self._extract_keywords(page_data.get("metadata", {})),
                            "page_type": page_data.get("metadata", {}).get("page_type", "unknown"),
                            "upload_timestamp": datetime.now().isoformat(),
                            "document_group": document_group
                        }
                        all_documents.append(doc)
                        total_pages += 1
                        
                    except Exception as e:
                        print(f"Erro ao processar página {page_data.get('page_number', '?')} de {file_name}: {e}")
                        continue
                
            except Exception as e:
                print(f"Erro ao processar PDF {file_name}: {e}")
                continue
        
        # Upload em lotes para Azure AI Search
        successful = 0
        failed = 0
        
        for i in range(0, len(all_documents), batch_size):
            batch = all_documents[i:i + batch_size]
            try:
                result = self.search_client.upload_documents(documents=batch)
                
                # Contar sucessos e falhas
                for r in result:
                    if r.succeeded:
                        successful += 1
                    else:
                        failed += 1
                        print(f"Falha ao indexar documento: {r.key}")
                
                print(f"Upload do lote {i//batch_size + 1}: {len(batch)} documentos")
                
            except Exception as e:
                print(f"Erro no upload do lote: {e}")
                failed += len(batch)
        
        return {
            "total_documents": len(pdf_files),
            "total_pages": total_pages,
            "successful": successful,
            "failed": failed,
            "document_names": document_names
        }
    
    def search_documents(self, 
                        query: str, 
                        top: int = 10,
                        document_group: Optional[str] = None,
                        document_name: Optional[str] = None) -> List[Dict]:
        """
        Busca documentos usando busca vetorial híbrida.
        
        Args:
            query: Texto da consulta
            top: Número máximo de resultados
            document_group: Filtrar por grupo de documentos (opcional)
            document_name: Filtrar por nome de documento específico (opcional)
        
        Returns:
            Lista de documentos encontrados com seus scores de relevância
        """
        # Gerar embedding da query
        query_embedding = self.embeddings.embed_query(query)
        
        # Construir filtros
        filters = []
        if document_group:
            filters.append(f"document_group eq '{document_group}'")
        if document_name:
            filters.append(f"document_name eq '{document_name}'")
        filter_string = " and ".join(filters) if filters else None
        
        # Executar busca híbrida (vetorial + textual)
        try:
            results = self.search_client.search(
                search_text=query,
                vector_queries=[{
                    "vector": query_embedding,
                    "k_nearest_neighbors": top,
                    "fields": "content_vector"
                }],
                filter=filter_string,
                top=top,
                select=["id", "document_name", "page_number", "content", 
                       "metadata_summary", "main_topics", "document_group"]
            )
            
            documents = []
            for result in results:
                documents.append({
                    "id": result["id"],
                    "document_name": result["document_name"],
                    "page_number": result["page_number"],
                    "content": result["content"],
                    "metadata_summary": result.get("metadata_summary", ""),
                    "main_topics": result.get("main_topics", []),
                    "document_group": result.get("document_group", ""),
                    "relevance_score": result.get("@search.score", 0)
                })
            
            return documents
            
        except Exception as e:
            print(f"Erro na busca: {e}")
            return []
    
    def delete_document(self, document_name: str) -> int:
        """
        Remove todas as páginas de um documento específico do índice.
        
        Args:
            document_name: Nome do documento a ser removido
        
        Returns:
            Número de documentos removidos
        """
        try:
            # Buscar todos os documentos com esse nome
            results = self.search_client.search(
                search_text="*",
                filter=f"document_name eq '{document_name}'",
                select=["id"],
                include_total_count=True
            )
            
            ids_to_delete = [{"id": doc["id"]} for doc in results]
            
            if not ids_to_delete:
                print(f"Nenhum documento encontrado com o nome: {document_name}")
                return 0
            
            # Deletar documentos
            delete_result = self.search_client.delete_documents(documents=ids_to_delete)
            
            deleted_count = sum(1 for r in delete_result if r.succeeded)
            print(f"Removidos {deleted_count} documentos do índice para: {document_name}")
            
            return deleted_count
            
        except Exception as e:
            print(f"Erro ao deletar documento {document_name}: {e}")
            return 0
    
    def delete_document_group(self, document_group: str) -> int:
        """
        Remove todos os documentos de um grupo específico.
        
        Args:
            document_group: Nome do grupo a ser removido
        
        Returns:
            Número de documentos removidos
        """
        try:
            # Buscar todos os documentos do grupo
            results = self.search_client.search(
                search_text="*",
                filter=f"document_group eq '{document_group}'",
                select=["id"],
                include_total_count=True
            )
            
            ids_to_delete = [{"id": doc["id"]} for doc in results]
            
            if not ids_to_delete:
                print(f"Nenhum documento encontrado no grupo: {document_group}")
                return 0
            
            # Deletar documentos
            delete_result = self.search_client.delete_documents(documents=ids_to_delete)
            
            deleted_count = sum(1 for r in delete_result if r.succeeded)
            print(f"Removidos {deleted_count} documentos do grupo: {document_group}")
            
            return deleted_count
            
        except Exception as e:
            print(f"Erro ao deletar grupo {document_group}: {e}")
            return 0
    
    def delete_old_documents(self, days_old: int = 30) -> int:
        """
        Remove documentos mais antigos que X dias.
        
        Args:
            days_old: Número de dias (padrão: 30)
        
        Returns:
            Número de documentos removidos
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
            
            # Buscar documentos antigos
            results = self.search_client.search(
                search_text="*",
                filter=f"upload_timestamp lt '{cutoff_date}'",
                select=["id", "document_name", "upload_timestamp"],
                include_total_count=True
            )
            
            ids_to_delete = [{"id": doc["id"]} for doc in results]
            
            if not ids_to_delete:
                print(f"Nenhum documento encontrado mais antigo que {days_old} dias")
                return 0
            
            # Deletar documentos
            delete_result = self.search_client.delete_documents(documents=ids_to_delete)
            
            deleted_count = sum(1 for r in delete_result if r.succeeded)
            print(f"Removidos {deleted_count} documentos mais antigos que {days_old} dias")
            
            return deleted_count
            
        except Exception as e:
            print(f"Erro ao deletar documentos antigos: {e}")
            return 0
    
    def clear_index(self) -> int:
        """
        Remove TODOS os documentos do índice.
        
        ATENÇÃO: Esta operação é irreversível!
        
        Returns:
            Número de documentos removidos
        """
        try:
            # Buscar todos os documentos
            results = self.search_client.search(
                search_text="*",
                select=["id"],
                include_total_count=True
            )
            
            ids_to_delete = [{"id": doc["id"]} for doc in results]
            
            if not ids_to_delete:
                print("O índice já está vazio")
                return 0
            
            # Deletar todos os documentos
            delete_result = self.search_client.delete_documents(documents=ids_to_delete)
            
            deleted_count = sum(1 for r in delete_result if r.succeeded)
            print(f"Removidos {deleted_count} documentos do índice (limpeza completa)")
            
            return deleted_count
            
        except Exception as e:
            print(f"Erro ao limpar índice: {e}")
            return 0
    
    def get_index_stats(self) -> Dict:
        """
        Retorna estatísticas do índice.
        
        Returns:
            Dict com estatísticas:
            {
                "total_documents": int,
                "document_groups": List[str],
                "document_names": List[str],
                "oldest_document": str,
                "newest_document": str
            }
        """
        try:
            # Buscar todos os documentos para estatísticas
            results = self.search_client.search(
                search_text="*",
                select=["document_name", "document_group", "upload_timestamp"],
                include_total_count=True
            )
            
            document_groups = set()
            document_names = set()
            timestamps = []
            
            for doc in results:
                document_groups.add(doc.get("document_group", "unknown"))
                document_names.add(doc.get("document_name", "unknown"))
                timestamps.append(doc.get("upload_timestamp", ""))
            
            timestamps = [t for t in timestamps if t]
            oldest = min(timestamps) if timestamps else None
            newest = max(timestamps) if timestamps else None
            
            return {
                "total_documents": len(list(results)),
                "document_groups": list(document_groups),
                "document_names": list(document_names),
                "oldest_document": oldest,
                "newest_document": newest
            }
            
        except Exception as e:
            print(f"Erro ao obter estatísticas: {e}")
            return {}


# Exemplo de uso
if __name__ == "__main__":
    # Configuração (substitua com suas credenciais)
    SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
    INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "pdf-documents-index")
    API_KEY = os.getenv("AZURE_SEARCH_API_KEY", "your-api-key")
    
    # Inicializar indexador
    indexer = AzurePDFIndexer(
        search_endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        api_key=API_KEY
    )
    
    # Exemplo 1: Indexar múltiplos PDFs
    # pdf_files = [file1, file2, file3]  # Lista de arquivos PDF
    # resultado = indexer.index_multiple_pdfs(
    #     pdf_files=pdf_files,
    #     document_group="contratos",
    #     batch_size=100
    # )
    # print(f"Indexação concluída: {resultado}")
    
    # Exemplo 2: Buscar documentos
    # resultados = indexer.search_documents(
    #     query="Quais são os termos do contrato?",
    #     top=5,
    #     document_group="contratos"
    # )
    # print(f"Encontrados {len(resultados)} documentos")
    
    # Exemplo 3: Remover um documento específico
    # removidos = indexer.delete_document("contrato_2024.pdf")
    # print(f"Removidos {removidos} documentos")
    
    # Exemplo 4: Remover grupo de documentos
    # removidos = indexer.delete_document_group("contratos")
    # print(f"Removidos {removidos} documentos do grupo")
    
    # Exemplo 5: Remover documentos antigos (mais de 30 dias)
    # removidos = indexer.delete_old_documents(days_old=30)
    # print(f"Removidos {removidos} documentos antigos")
    
    # Exemplo 6: Limpar todo o índice
    # removidos = indexer.clear_index()
    # print(f"Removidos {removidos} documentos (limpeza completa)")
    
    # Exemplo 7: Obter estatísticas do índice
    # stats = indexer.get_index_stats()
    # print(f"Estatísticas: {stats}")

