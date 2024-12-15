import hashlib
import logging
import os
from transformers.utils import is_torch_cuda_available, is_torch_mps_available
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LangDocument
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_chroma import Chroma
from langchain_community.llms import Ollama
from langchain.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_embedding(device):
    model_name = "gte-large-zh"  # 可根据需要替换成合适的中文嵌入模型
    embedding = HuggingFaceBgeEmbeddings(
        model_name=model_name,
        model_kwargs={'device': device},
        encode_kwargs={'normalize_embeddings': True},
        query_instruction="为文本生成向量表示用于文本检索"
    )
    logger.info("向量化模型加载完成")
    return embedding

def get_llm():
    # 配置LLM（如Ollama），需要确保后台有 Ollama server在运行，并加载gemma2:9b模型
    llm = Ollama(base_url="http://127.0.0.1:11434", model="gemma2:9b", temperature=0)
    logger.info("LLM模型配置完成")
    return llm

def process_rag(content, question, user):
    device = "cuda" if is_torch_cuda_available() else "mps" if is_torch_mps_available() else "cpu"
    embedding = get_embedding(device)
    llm = get_llm()

    # 如果content为空，表示用户未上传文档，只使用LLM回答问题
    if not content or not content.strip():
        system_prompt = f"Answer the following question based solely on your own knowledge.\nQuestion: {question}\nAnswer:"
        result = llm(system_prompt)
        return {"answer": result}

    # 有上传文档时执行RAG流程
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )

    initial_doc = LangDocument(page_content=content)
    final_docs = splitter.split_documents([initial_doc])
    logger.info(f"文本分割完成，共生成 {len(final_docs)} 个块")

    user_db_dir = f'chroma_db/{user}'
    os.makedirs(user_db_dir, exist_ok=True)

    # 加载或创建Chroma数据库，并进行去重检查
    if os.listdir(user_db_dir):
        db = Chroma(persist_directory=user_db_dir, embedding_function=embedding)
        existing_ids = set(db._collection.get()['ids'])  # 获取已有文档ID列表

        new_docs = []
        new_ids = []
        for d in final_docs:
            doc_hash = hashlib.sha256(d.page_content.encode('utf-8')).hexdigest()
            if doc_hash not in existing_ids:
                new_docs.append(d)
                new_ids.append(doc_hash)

        if new_docs:
            db.add_documents(new_docs, ids=new_ids)
            logger.info(f"为用户 {user} 的数据库新增 {len(new_docs)} 个新文档块")
        else:
            logger.info(f"用户 {user} 上传的文档已存在，未新增文档块")
    else:
        # 第一次创建时，为每个文档块创建哈希ID
        doc_ids = []
        for d in final_docs:
            doc_hash = hashlib.sha256(d.page_content.encode('utf-8')).hexdigest()
            doc_ids.append(doc_hash)
        db = Chroma.from_documents(final_docs, embedding, ids=doc_ids, persist_directory=user_db_dir)
        logger.info(f"为用户 {user} 创建新的数据库")


    # 构建RAG链
    system_prompt = (
        "You are an AI assistant that provides accurate answers based on the provided context.\n"
        "Use the following pieces of retrieved context to answer the question.\n\n"
        "Answer the question in Chinese"
        "{context}\n\n"
        "Question: {input}\n"
        "Answer:"
    )
    prompt = ChatPromptTemplate.from_template(system_prompt)
    question_answer_chain = create_stuff_documents_chain(llm, prompt)

    retriever = db.as_retriever(search_type="mmr", search_kwargs={'k': 2, 'fetch_k': 10, 'lambda_mult': 0.5})
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    logger.info("检索增强生成链创建完成")

    result = rag_chain.invoke({"input": question})
    logger.info(f"RAG链返回结果: {result}")

    return {"answer": result['answer']}
