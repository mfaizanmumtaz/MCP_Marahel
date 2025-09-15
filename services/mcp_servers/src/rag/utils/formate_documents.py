async def extract_usefull_info(documents):
    """
    Extract useful information from the documents.
    """
    data = "\n".join([doc.page_content for doc in documents])
    return data