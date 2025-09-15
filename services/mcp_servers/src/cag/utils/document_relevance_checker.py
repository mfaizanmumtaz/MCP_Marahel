from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import Field
import concurrent.futures
from typing import List


def filter_relevant_documents(
    user_question: str, retrieved_documents: List, llm_model
) -> List:
    # Data model
    class GradeDocuments(BaseModel):
        """Binary score for relevance check on retrieved documents."""

        binary_score: str = Field(
            description="Documents are relevant to the question, 'yes' or 'no'"
        )

    # LLM with function call

    structured_llm_grader = llm_model.with_structured_output(GradeDocuments)

    # Prompt
    system = """You are a grader assessing relevance of a retrieved document to a user question. \n 
If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. \n
It does not need to be a stringent test. The goal is to filter out erroneous retrievals. \n
Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question."""
    grade_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            (
                "human",
                "Retrieved document: \n\n ```{document}``` \n\n User question: ```{question}```",
            ),
        ]
    )

    retrieval_grader = grade_prompt | structured_llm_grader

    def check_document_relevance(args):
        document, user_question = args
        print("Checking document relevance")
        score = retrieval_grader.invoke(
            {"question": user_question, "document": document.page_content}
        )
        if score.binary_score == "yes":
            return document
        return None

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Create args list for each document
        args = [(doc, user_question) for doc in retrieved_documents]

        # Map the check_document_relevance function across documents using threads
        results = list(executor.map(check_document_relevance, args))

    # Filter out None results
    relevant_documents = [doc for doc in results if doc is not None]

    print(f"Found {len(relevant_documents)} relevant documents")
    return relevant_documents
