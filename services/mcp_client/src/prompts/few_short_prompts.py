from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

examples = [
    # Example 1: Using CAG knowledge base for document information
    HumanMessage(
        "What does this document is about?", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "cag_knowledge_base", "args": {"user_query": "What does this document is about?"}, "id": "call_1"}
        ],
    ),
    ToolMessage('''The document you uploaded is titled "AI Engineer Roadmap." It is about outlining the essential skills, knowledge areas, and learning paths for aspiring AI engineers. The document covers topics such as the roles and differences between AI and ML engineers, large language models (LLMs), prompt engineering, AI safety and ethics, the use of pre-trained models, vector databases, retrieval-augmented generation (RAG), and multimodal AI applications. It also provides resources for further learning and related roadmaps in AI and data science.

If you want more detailed information or have specific questions about the document, please let me know!''', tool_call_id="call_1"),
    AIMessage(
        '''The document you uploaded is titled "AI Engineer Roadmap." It is about outlining the essential skills, knowledge areas, and learning paths for aspiring AI engineers. The document covers topics such as the roles and differences between AI and ML engineers, large language models (LLMs), prompt engineering, AI safety and ethics, the use of pre-trained models, vector databases, retrieval-augmented generation (RAG), and multimodal AI applications. It also provides resources for further learning and related roadmaps in AI and data science.

If you want more detailed information or have specific questions about the document, please let me know!''',
        name="example_assistant",
    ),

    # Example 2: Using RAG for specific information retrieval
    HumanMessage(
        "Can you find specific information about machine learning algorithms in my documents?", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "rag_knowledge_base", "args": {"user_query": "machine learning algorithms"}, "id": "call_2"}
        ],
    ),
    ToolMessage('''{"status": "success", "data": "Based on your documents, here are the key machine learning algorithms mentioned: 1) Supervised Learning: Linear Regression, Decision Trees, Random Forest, Support Vector Machines, Neural Networks. 2) Unsupervised Learning: K-means clustering, Hierarchical clustering, Principal Component Analysis (PCA). 3) Deep Learning: Convolutional Neural Networks (CNNs), Recurrent Neural Networks (RNNs), Transformer models. The documents emphasize that choosing the right algorithm depends on your data type, problem complexity, and performance requirements."}''', tool_call_id="call_2"),
    AIMessage(
        '''Based on your documents, here are the key machine learning algorithms mentioned:

**Supervised Learning:**
- Linear Regression
- Decision Trees
- Random Forest
- Support Vector Machines
- Neural Networks

**Unsupervised Learning:**
- K-means clustering
- Hierarchical clustering
- Principal Component Analysis (PCA)

**Deep Learning:**
- Convolutional Neural Networks (CNNs)
- Recurrent Neural Networks (RNNs)
- Transformer models

The documents emphasize that choosing the right algorithm depends on your data type, problem complexity, and performance requirements.''',
        name="example_assistant",
    ),

    # Example 3: Requesting summarization when available
    HumanMessage(
        "Can you provide a summary of all my documents?", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "get_summarization", "args": {}, "id": "call_3"}
        ],
    ),
    ToolMessage('''{"summary": "Your document collection contains comprehensive information about AI and machine learning engineering. The main themes include: 1) Technical Skills - Programming languages (Python, R), frameworks (TensorFlow, PyTorch), and cloud platforms. 2) AI/ML Concepts - Deep learning, neural networks, natural language processing, computer vision. 3) Data Management - Data preprocessing, feature engineering, model evaluation, and deployment strategies. 4) Career Development - Different roles in AI/ML, required skills, and learning pathways. The documents emphasize practical application and provide roadmaps for both beginners and experienced professionals.", "status": "success"}''', tool_call_id="call_3"),
    AIMessage(
        '''Here's a comprehensive summary of all your documents:

Your document collection contains comprehensive information about AI and machine learning engineering. The main themes include:

**1) Technical Skills**
- Programming languages (Python, R)
- Frameworks (TensorFlow, PyTorch)
- Cloud platforms

**2) AI/ML Concepts**
- Deep learning and neural networks
- Natural language processing
- Computer vision

**3) Data Management**
- Data preprocessing
- Feature engineering
- Model evaluation and deployment strategies

**4) Career Development**
- Different roles in AI/ML
- Required skills and learning pathways

The documents emphasize practical application and provide roadmaps for both beginners and experienced professionals.''',
        name="example_assistant",
    ),

    # Example 4: Translation request when available
    HumanMessage(
        "Can you translate my documents to Spanish?", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "get_translation", "args": {"target_language": "Spanish"}, "id": "call_4"}
        ],
    ),
    ToolMessage('''{"translation": "Sus documentos contienen información integral sobre ingeniería de IA y aprendizaje automático. Los temas principales incluyen: 1) Habilidades Técnicas - Lenguajes de programación (Python, R), frameworks (TensorFlow, PyTorch), y plataformas en la nube. 2) Conceptos de IA/ML - Aprendizaje profundo, redes neuronales, procesamiento de lenguaje natural, visión por computadora. 3) Gestión de Datos - Preprocesamiento de datos, ingeniería de características, evaluación de modelos, y estrategias de implementación.", "target_language": "Spanish", "status": "success"}''', tool_call_id="call_4"),
    AIMessage(
        '''Sus documentos contienen información integral sobre ingeniería de IA y aprendizaje automático. Los temas principales incluyen:

**1) Habilidades Técnicas**
- Lenguajes de programación (Python, R)
- Frameworks (TensorFlow, PyTorch)
- Plataformas en la nube

**2) Conceptos de IA/ML**
- Aprendizaje profundo y redes neuronales
- Procesamiento de lenguaje natural
- Visión por computadora

**3) Gestión de Datos**
- Preprocesamiento de datos
- Ingeniería de características
- Evaluación de modelos y estrategias de implementación

Los documentos enfatizan la aplicación práctica y proporcionan hojas de ruta tanto para principiantes como para profesionales experimentados.''',
        name="example_assistant",
    ),

    # Example 5: Handling unavailable tools gracefully
    HumanMessage(
        "Can you summarize my documents?", name="example_user"
    ),
    AIMessage(
        '''I apologize, but I don't have access to the summarization tool at the moment. However, I can help you by:

1. Using the CAG knowledge base to get general information about your documents
2. Using the RAG knowledge base to find specific information you're looking for
3. Answering specific questions about your content

Would you like me to help you with any of these alternatives, or do you have a specific question about your documents?''',
        name="example_assistant",
    ),

    # Example 6: Permission-based tool access denial
    HumanMessage(
        "Translate this to French", name="example_user"
    ),
    AIMessage(
        '''I don't have access to the translation tool for your account. Please contact your administrator to enable translation access.

In the meantime, I can help you with:
- Retrieving information from your knowledge base
- Finding specific content using search
- Answering questions about your documents

Is there anything else I can help you with?''',
        name="example_assistant",
    ),

    # Example 7: Using summarization with full access
    HumanMessage(
        "Give me a quick summary of everything I have", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "get_summarization", "args": {}, "id": "call_5"}
        ],
    ),
    ToolMessage('''{"summary": "Your knowledge base contains extensive documentation about software development practices, including: 1) Project Management - Agile methodologies, sprint planning, and team collaboration tools. 2) Technical Architecture - Microservices design, API development, database optimization, and cloud infrastructure. 3) Code Quality - Testing strategies, code reviews, continuous integration/deployment pipelines. 4) Security - Authentication, authorization, data encryption, and security best practices. 5) Performance - System monitoring, caching strategies, and optimization techniques. The documents provide both theoretical concepts and practical implementation guides.", "status": "success"}''', tool_call_id="call_5"),
    AIMessage(
        '''Here's a quick summary of everything in your knowledge base:

Your knowledge base contains extensive documentation about software development practices, including:

**1) Project Management**
- Agile methodologies
- Sprint planning and team collaboration tools

**2) Technical Architecture**
- Microservices design
- API development
- Database optimization
- Cloud infrastructure

**3) Code Quality**
- Testing strategies
- Code reviews
- Continuous integration/deployment pipelines

**4) Security**
- Authentication and authorization
- Data encryption
- Security best practices

**5) Performance**
- System monitoring
- Caching strategies
- Optimization techniques

The documents provide both theoretical concepts and practical implementation guides.''',
        name="example_assistant",
    ),

    # Example 8: Using translation with full access
    HumanMessage(
        "Can you translate my software documentation to Arabic?", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "get_translation", "args": {"target_language": "Arabic"}, "id": "call_6"}
        ],
    ),
    ToolMessage('''{"translation": "تحتوي قاعدة معارفك على وثائق شاملة حول ممارسات تطوير البرمجيات، بما في ذلك: 1) إدارة المشاريع - منهجيات أجايل، تخطيط السبرينت، وأدوات التعاون الجماعي. 2) الهندسة التقنية - تصميم الخدمات المصغرة، تطوير واجهات برمجة التطبيقات، تحسين قواعد البيانات، والبنية التحتية السحابية. 3) جودة الكود - استراتيجيات الاختبار، مراجعات الكود، وخطوط أنابيب التكامل/النشر المستمر.", "target_language": "Arabic", "status": "success"}''', tool_call_id="call_6"),
    AIMessage(
        '''تم ترجمة وثائق البرمجيات الخاصة بك إلى العربية:

تحتوي قاعدة معارفك على وثائق شاملة حول ممارسات تطوير البرمجيات، بما في ذلك:

**1) إدارة المشاريع**
- منهجيات أجايل
- تخطيط السبرينت وأدوات التعاون الجماعي

**2) الهندسة التقنية**
- تصميم الخدمات المصغرة
- تطوير واجهات برمجة التطبيقات
- تحسين قواعد البيانات
- البنية التحتية السحابية

**3) جودة الكود**
- استراتيجيات الاختبار
- مراجعات الكود
- خطوط أنابيب التكامل/النشر المستمر

الوثائق تقدم المفاهيم النظرية والأدلة العملية للتنفيذ.''',
        name="example_assistant",
    ),

    # Example 9: Combining multiple tools with full access
    HumanMessage(
        "First summarize my documents, then translate the summary to German", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "get_summarization", "args": {}, "id": "call_7"}
        ],
    ),
    ToolMessage('''{"summary": "Your documents cover comprehensive web development topics including: Frontend frameworks (React, Vue, Angular), Backend technologies (Node.js, Python, Java), Database management (SQL, NoSQL), DevOps practices (Docker, Kubernetes, CI/CD), and modern development workflows.", "status": "success"}''', tool_call_id="call_7"),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "get_translation", "args": {"target_language": "German"}, "id": "call_8"}
        ],
    ),
    ToolMessage('''{"translation": "Ihre Dokumente decken umfassende Webentwicklungsthemen ab, einschließlich: Frontend-Frameworks (React, Vue, Angular), Backend-Technologien (Node.js, Python, Java), Datenbankmanagement (SQL, NoSQL), DevOps-Praktiken (Docker, Kubernetes, CI/CD) und moderne Entwicklungsworkflows.", "target_language": "German", "status": "success"}''', tool_call_id="call_8"),
    AIMessage(
        '''I've summarized your documents and translated them to German:

**Summary:** Your documents cover comprehensive web development topics including: Frontend frameworks (React, Vue, Angular), Backend technologies (Node.js, Python, Java), Database management (SQL, NoSQL), DevOps practices (Docker, Kubernetes, CI/CD), and modern development workflows.

**German Translation:** Ihre Dokumente decken umfassende Webentwicklungsthemen ab, einschließlich: Frontend-Frameworks (React, Vue, Angular), Backend-Technologien (Node.js, Python, Java), Datenbankmanagement (SQL, NoSQL), DevOps-Praktiken (Docker, Kubernetes, CI/CD) und moderne Entwicklungsworkflows.''',
        name="example_assistant",
    )
    ,
    # HumanMessage(content="Translate the following document.", name="example_user"),
    # AIMessage(content="Please provide the target language in which you want to translate the document.", name="example_assistant"),
    # HumanMessage(content="German", name="example_user"),
    # AIMessage(content="I've translated the document to German: Ihre Dokumente decken umfassende Webentwicklungsthemen ab, einschließlich: Frontend-Frameworks (React, Vue, Angular), Backend-Technologien (Node.js, Python, Java), Datenbankmanagement (SQL, NoSQL), DevOps-Praktiken (Docker, Kubernetes, CI/CD) und moderne Entwicklungsworkflows.", name="example_assistant"),
]

