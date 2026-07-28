import logging
from langchain_core.messages import SystemMessage, HumanMessage
from app.ai.llm.factory import get_llm
from app.company_support.vectorstore import get_company_retriever

logger = logging.getLogger("app.company_support.service")

def execute_company_support_rag(query: str, history: list[dict] = None) -> dict:
    """
    Executes the RAG pipeline for company support:
    1. Retrieve relevant documentation chunks from the company support vectorstore/retriever.
    2. Format the context and build a grounding prompt.
    3. Generate the response using the existing LLM provider.
    """
    try:
        retriever = get_company_retriever()
        
        # 1. Retrieve documents
        # Support both Chroma retriever (which uses invoke) and fallback retriever (which also uses invoke)
        try:
            docs = retriever.invoke(query)
        except Exception as e:
            logger.warning(f"Error retrieving documents: {e}")
            docs = []

        # Extract context text and sources
        context_chunks = []
        sources = set()
        for doc in docs:
            context_chunks.append(doc.page_content)
            source = doc.metadata.get("source", "Unknown Source")
            sources.add(source)

        context_text = "\n\n---\n\n".join(context_chunks) if context_chunks else "No relevant documentation found."
        
        # 2. Build the system prompt enforcing strict grounding
        system_prompt = (
            "You are the official SupportAI Company Assistant. Your task is to help the user with questions "
            "about company policies, standard operating procedures (SOPs), FAQs, and general procedures.\n\n"
            "Strict Grounding Rule:\n"
            "Answer the question based ONLY on the provided context below. Do not assume, extrapolate, or use outside knowledge. "
            "If the context does not contain enough information to answer the question, respond exactly with:\n"
            "\"I'm sorry, but I couldn't find that information in our official company documentation. Let me know if you have other questions!\"\n\n"
            f"--- Context ---\n{context_text}\n--- End of Context ---"
        )
        
        # Build messages list
        messages = [SystemMessage(content=system_prompt)]
        
        # Append chat history if provided
        if history:
            # Keep history to last 6 messages to stay lightweight
            for msg in history[-6:]:
                role = msg.get("role")
                content = msg.get("content")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(HumanMessage(content=content)) # HumanMessage or AIMessage depends on schema, but let's be safe: HumanMessage works for input formatting, or we can use AIMessage if imported
                    
        # Add the current query
        messages.append(HumanMessage(content=query))
        
        # 3. Call the routing LLM
        llm = get_llm()
        response_text = llm.invoke(messages)
        
        return {
            "query": query,
            "response": response_text.strip(),
            "sources": list(sources),
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error in company support RAG pipeline: {e}", exc_info=True)
        return {
            "query": query,
            "response": "I'm sorry, I encountered an internal error trying to process your request. Please try again.",
            "sources": [],
            "status": "error",
            "detail": str(e)
        }
