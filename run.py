from langchain_core.documents import Document


docs_all = [Document(page_content="test data",metadata={"page":1})]

serialized = [doc.__dict__ for doc in docs_all]
print(serialized)