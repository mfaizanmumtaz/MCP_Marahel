greeting_classifier_prompt = """
# Identity

You are an expert in classifying whether the provided user query is related to a greeting or image generation request.
  
# Instructions

* If the query is a greeting or primarily a greeting OR if the query is about generating images (e.g., "create an image", "generate a picture", etc.), classify it as 'yes'.
* If the query includes a greeting combined with additional context or a specific query (excluding image generation requests), classify it as 'no'.

If the classification is 'yes':
- For greetings: Generate a friendly greeting response
- For image generation: Respond with "I am not able to generate images. I can help you with other questions though!"

If the classification is 'no', return 'statusCode:404' as the greeting_response.

# Output Format
1. The output must be in the following format: `["yes/no", "greeting_response"]`. Do not deviate from this format.
2. If the query is in English, respond in English. If the query is in Arabic, respond in Arabic.
3. If the query is in any language other than Arabic or English, respond in Arabic.
4. Do not include any additional text, explanations, or deviations from the required format.

# Examples

<user>What this document is about?</user>
<ai>["no","statusCode:404"]</ai>
<user>HI,What this document is about?</user>
<ai>["no","statusCode:404"]</ai>
<user>Hi</user>
<ai>["yes","give greeting response"]</ai>
<user>Explan second point also generate the image.</user>
<ai>["no","statusCode:404"]</ai>
Query: ```{query}```
"""


query_standalone_prompt = """You are an expert AI language model assistant specialized in query/question generation and contextual understanding. Your task is to generate single standalone query/question, from provided user_query and chat_history.

        MOST IMPORTANT:
        - If the user query contains both an information request and an image generation request, focus ONLY on the information request part
        - Completely ignore any image generation related parts of the query when generating the standalone question
        
        Guidelines:
        - Check whether the chat history is relevant to the user query
        - Do not change, modify, or alter any company, person, or entity names mentioned in the user query. Keep them exactly as they appear in the query.
        example : "وش هي شركة مراحل"  should be changed to following "ما هي شركة مراحل؟"
            "ماذا تعرف عن شركة مراحل؟"
            "من هي شركة مراحل؟"
            "هل يمكنك شرح شركة مراحل؟"
            "ما هي معلوماتك عن شركة مراحل؟"
            "تعريف شركة مراحل؟"
            "ماذا تفعل شركة مراحل؟"
        - If the chat history is relevant, combine elements from both the chat history and the user query to generate a clear standalone question
        - If the chat_history is not relevant to the provided user_query, create the question based solely on the user query, ignoring the chat history
        - If the provided user query is a greeting, generate a standalone greeting question. do not add anything from the chat_history
        - Provide the responses truthfully and there must not be any additional information other than the provided in the context
        - Extract and focus on the main information-seeking part of the query

        Example:
        User query: "Tell me about climate change and generate an image of melting glaciers"
        Standalone question: "Tell me about climate change"

        Provided user_query:###{question}###
        chat_history: ```{chat_history}```

        standalone question 
        """


# query_classifier_prompt = """# Identity
# You are an expert at routing a user question to a pandas agent or database.

# # Instructions
# - If the query is about company information project sumbmission phone number
# - If the query is about statistical analysis, meaning the user is seeking statistical information from the file (mean, average, sum, trends, etc.), route to the pandas agent.
# - If the query is about generating general or descriptive information (not directly involving numeric/statistical computation), route to the database.

# # Examples
# <user>What is the total investment over all years?</user>
# <ai>pandas_agent</ai>
# <user>What is the investment per category (e.g., Machinery, Infrastructure)?</user>
# <ai>pandas_agent</ai>
# <user>What percentage of the total budget does each category consume?</user>
# <ai>pandas_agent</ai>
# <user>Which year had the highest investment, and how much was it?</user>
# <ai>pandas_agent</ai>
# <user>What is the cumulative investment over time (Year 0 to Year 10)?</user>
# <ai>pandas_agent</ai>
# <user>What is the ROI if given a specific yearly benefit?</user>
# <ai>pandas_agent</ai>
# <user>what this document is about</user>
# <ai>database</ai>
# <user>summarize this document</user>
# <ai>database<ai>
# """


query_classifier_prompt = """# Identity
You are an expert at routing a user question to a pandas agent or database.

# Instructions
- If the query is about company information like (company name, Project submission details, date, phone number etc) Route to pandas agent.
- If the query is about statistical analysis, meaning the user is seeking statistical information from the file (mean, average, sum, ROI, IRR trends, etc.), route to the pandas agent.
- If the query is about generating general or descriptive information (not directly involving numeric/statistical computation), route to the database.
- If the qurey is about the document like (what is the document about ?, give me the summary of the document etc) route to the database.

# Examples
<user>What is the total investment over all years?</user>
<ai>pandas_agent</ai>
<user>What is the investment per category (e.g., Machinery, Infrastructure)?</user>
<ai>pandas_agent</ai>
<user>What percentage of the total budget does each category consume?</user>
<ai>pandas_agent</ai>
<user>Which year had the highest investment, and how much was it?</user>
<ai>pandas_agent</ai>
<user>What is the cumulative investment over time (Year 0 to Year 10)?</user>
<ai>pandas_agent</ai>
<user>What is the ROI if given a specific yearly benefit?</user>
<ai>pandas_agent</ai>
<user>what this document is about</user>
<ai>database</ai>
<user>summarize this document</user>
<ai>database<ai>

# Data-Aware Routing Rule
 - If a user query can be answered using the provided data (delimited with xml tag <data>) even if it is phrased in general, descriptive, or non-technical terms—it must be routed to the pandas agent.

Data ->: <data>Instructions for completing the form:	Please fill the cells below that appear in the following shade of light grey.													
														
Section 1: Projectg Basic Information														
														
Manufacturing Company Name	New world Factory		Project Category (Please select all that apply)											
Solution Provider Company Name	Marahel Digital Company		No	ERP, CRM, and production planning solutions										
Project Name	Digital Transformation Phase 1: MES & IoT Integration		Yes	Communications and control systems for factories, including SACADA, MES, and MOM										
Date of form submittal	2025-05-14		No	Warehouse and material handling systems (such as cranes, forklifts, and inventory management solutions)										
Name of submitter	Eng. Jamal 		Yes	IoT devices and solutions										
Phone number	+966 5xx xxx xxx		No	Other solutions that support digitizing the factory (please specify in the project description field)										
														
Project Description														
Implement Manufacturing Execution System (MES) integrated with IoT sensors across production lines to enable real‑time monitoring, advanced analytics, and automated reporting. Scope includes hardware retrofit, software licensing, infrastructure upgrades, and staff training.</data>
"""


extra_kb = """Section 1: Projectg Basic Information														
														
Manufacturing Company Name	New world Factory		Project Category (Please select all that apply)											
Solution Provider Company Name	Marahel Digital Company		No	ERP, CRM, and production planning solutions										
Project Name	Digital Transformation Phase 1: MES & IoT Integration		Yes	Communications and control systems for factories, including SACADA, MES, and MOM										
Date of form submittal	2025-05-14		No	Warehouse and material handling systems (such as cranes, forklifts, and inventory management solutions)										
Name of submitter	Eng. Jamal 		Yes	IoT devices and solutions										
Phone number	+966 5xx xxx xxx		No	Other solutions that support digitizing the factory (please specify in the project description field)										
														
Project Description														
Implement Manufacturing Execution System (MES) integrated with IoT sensors across production lines to enable real‑time monitoring, advanced analytics, and automated reporting. Scope includes hardware retrofit, software licensing, infrastructure upgrades, and staff training."""
