import streamlit as st
import uuid
from langchain_core.messages import HumanMessage
#from langchain_community.callbacks.streamlit import StreamlitCallbackHandler
from langgraph.checkpoint.memory import MemorySaver
from .document_process import DocumentProcessor
from .graph_builder import PDFAgentBuilder

##########
def save_to_json(data, output_file):
    import json
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@st.cache_resource
def get_memory_saver():
    return MemorySaver()

def run(text, config):
    messages = [HumanMessage(content=text)]
    return st.session_state["agent"].invoke({"messages": messages}, config)

def build_page(is_authenticated: bool):
    if is_authenticated:
        if "step" not in st.session_state:
            st.session_state["step"] = "form"        

        if st.session_state["step"] == "form":
            st.header("Configuração Inicial")

            with st.form("setup_form"):
                uploaded_file = st.file_uploader("Carregar PDF", type=['pdf'], accept_multiple_files=False)                
                if st.form_submit_button("Iniciar Chat com documentos") and uploaded_file:
                    try:
                        processor = DocumentProcessor([uploaded_file])
                        pdf_docs = processor.process_documents()
                        st.session_state["pdf_docs"] = pdf_docs
                        
                        if "agent" not in st.session_state:                        
                            workflow_builder = PDFAgentBuilder(memory_saver=get_memory_saver())
                            agent = workflow_builder.build()
                            st.session_state["agent"] = agent
                        st.session_state["step"] = "chat"
                        st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao processar o documento: {str(e)}")
                        st.error(f"Tipo do erro: {type(e)}")
                else:
                    st.error("Por favor, preencha todos os campos.")

        elif st.session_state["step"] == "chat":
            st.header("ChatPDF")

            message_container = st.container(height=600)

            input_container = st.container()
            
            if "chat_history" not in st.session_state:
                st.session_state["chat_history"] = []

            if "thread_id" not in st.session_state:
                st.session_state["thread_id"] = str(uuid.uuid4())
                config = {"configurable": {"thread_id": st.session_state["thread_id"]}}
                st.session_state["agent"].update_state(config,values={"pdf_data": st.session_state["pdf_docs"]})

            with input_container:
                col1, col2 = st.columns([1, 12])
                
                if col1.button(label="🗑️"):
                    st.session_state["chat_history"] = []

                    if "thread_id" in st.session_state:
                        del st.session_state["thread_id"]                    
                    if "agent" in st.session_state:
                        del st.session_state["agent"]
                    
                    st.session_state["step"] = "form"
                    st.rerun()
                
                prompt = col2.chat_input("Digite sua pergunta:")

            if prompt:
                st.session_state["chat_history"].append({"role": "user", "content": prompt})
                
                #st_callback = StreamlitCallbackHandler(st.container())

                config = {
                    "configurable": {
                        "thread_id": st.session_state["thread_id"]
                    }#,
                    #"callbacks": [st_callback]
                }

                try:
                    response = run(prompt, config)
                    st.session_state["chat_history"].append(
                        {"role": "assistant", "content": response["messages"][-1].content}
                    )
                    st.rerun() 

                except Exception as e:
                    st.error(f"Erro durante a execução: {e}")
            
            with message_container:
                st.markdown("""
                    <style>
                        .stContainer {
                            max-height: 600px;
                            max-width: 800px;
                            overflow-y: auto;
                            padding-right: 20px;
                        }
                    </style>
                """, unsafe_allow_html=True)

                # if "pdf_data" in st.session_state:
                #     with st.expander("Informações do PDF"):
                #         st.write(f"Descrição: {st.session_state['pdf_data']['description']}")

                for msg in st.session_state["chat_history"]:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

if __name__ == "__main__":
    build_page(is_authenticated=True)