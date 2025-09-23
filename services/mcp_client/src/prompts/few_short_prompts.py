from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

examples = [
    # Example 1: Using CAG knowledge base for breastfeeding information
    HumanMessage(
        "What are the benefits of breastfeeding for the baby?", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "cag_knowledge_base", "args": {"user_query": "What are the benefits of breastfeeding for the baby?"}, "id": "call_1"}
        ],
    ),
    ToolMessage('''Breastfeeding provides numerous benefits for the baby including: breast milk contains all the nutrients the infant needs, easy digestion allows the baby to benefit optimally from breast milk, protects the baby from infections due to antibodies, supports mental and cognitive development, breast milk is always ready and requires no preparation or warming, and prevents allergies that may be caused by artificial feeding.''', tool_call_id="call_1"),
    AIMessage(
        '''Breastfeeding provides numerous benefits for the baby including:

- **Complete Nutrition:** Breast milk contains all the nutrients the infant needs
- **Easy Digestion:** Allows the baby to benefit optimally from breast milk
- **Infection Protection:** Protects the baby from infections due to antibodies
- **Cognitive Development:** Supports mental and cognitive development
- **Convenience:** Breast milk is always ready and requires no preparation or warming
- **Allergy Prevention:** Prevents allergies that may be caused by artificial feeding

These benefits make breastfeeding the optimal choice for infant nutrition and development.''',
        name="example_assistant",
    ),

    # Example 2: Using RAG for specific breastfeeding information
    HumanMessage(
        "How do I know if my baby is getting enough milk?", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "rag_knowledge_base", "args": {"user_query": "signs baby getting enough milk"}, "id": "call_2"}
        ],
    ),
    ToolMessage('''{"status": "success", "data": "Two important indicators show your baby is getting enough milk: 1) The baby wets diapers 6-8 times per day (breast milk is 87% water), 2) Noticeable weight gain and growth. Additional signs include: 8-12 feeding sessions per day, 10-20 minutes per breast, you can hear the baby swallowing, and breasts feel empty and soft after effective feeding."}''', tool_call_id="call_2"),
    AIMessage(
        '''Here are the key signs that your baby is getting enough milk:

**Primary Indicators:**
- Baby wets diapers 6-8 times per day (breast milk is 87% water)
- Noticeable weight gain and growth

**Additional Signs:**
- 8-12 feeding sessions per day
- 10-20 minutes per breast during feeding
- You can hear the baby swallowing during feeds
- Breasts feel empty and soft after effective feeding

These indicators help ensure your baby is receiving adequate nutrition through breastfeeding.''',
        name="example_assistant",
    ),

    # Example 3: Requesting summarization for breastfeeding documents
    HumanMessage(
        "Can you provide a summary of all my breastfeeding documents?", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "get_summarization", "args": {}, "id": "call_3"}
        ],
    ),
    ToolMessage('''{"summary": "Your document collection contains comprehensive information about breastfeeding and infant care. The main themes include: 1) Breastfeeding Benefits - Health advantages for both mother and baby, including immune protection and bonding. 2) Proper Techniques - Correct latching, positioning, and feeding schedules. 3) Common Challenges - Solutions for nipple pain, engorgement, low milk supply, and nipple confusion. 4) Milk Production - Hormones involved, factors affecting supply, and natural ways to increase production. 5) Practical Guidance - Milk storage, pumping techniques, and transitioning to solid foods. The documents emphasize evidence-based practices and WHO recommendations.", "status": "success"}''', tool_call_id="call_3"),
    AIMessage(
        '''Here's a comprehensive summary of your breastfeeding documents:

Your document collection contains comprehensive information about breastfeeding and infant care. The main themes include:

**1) Breastfeeding Benefits**
- Health advantages for both mother and baby
- Immune protection and emotional bonding

**2) Proper Techniques**
- Correct latching and positioning
- Feeding schedules and duration

**3) Common Challenges**
- Solutions for nipple pain and engorgement
- Managing low milk supply and nipple confusion

**4) Milk Production**
- Hormones involved in lactation
- Natural ways to increase milk supply

**5) Practical Guidance**
- Milk storage and pumping techniques
- Transitioning to solid foods

The documents emphasize evidence-based practices and WHO recommendations for optimal breastfeeding success.''',
        name="example_assistant",
    ),

    # Example 4: Translation request for breastfeeding content to Arabic
    HumanMessage(
        "Can you translate my breastfeeding documents.", name="example_user"
    ),
    AIMessage(
        "Please provide the target language you would like your breastfeeding documents translated into.",
        name="example_assistant",
    ),
    HumanMessage(
        "Arabic", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "get_translation", "args": {"target_language": "Arabic"}, "id": "call_4"}
        ],
    ),
    ToolMessage('''{"translation": "تحتوي مجموعة وثائقك على معلومات شاملة حول الرضاعة الطبيعية ورعاية الرضع. تشمل المواضيع الرئيسية: 1) فوائد الرضاعة الطبيعية - المزايا الصحية للأم والطفل، بما في ذلك الحماية المناعية والترابط العاطفي. 2) التقنيات الصحيحة - الالتقام الصحيح، وضعيات الرضاعة، وجداول الإرضاع. 3) التحديات الشائعة - حلول لألم الحلمة، الاحتقان، قلة إدرار الحليب، وارتباك الحلمة. 4) إنتاج الحليب - الهرمونات المشاركة، العوامل المؤثرة على الإدرار، والطرق الطبيعية لزيادة الإنتاج.", "target_language": "Arabic", "status": "success"}''', tool_call_id="call_4"),
    AIMessage(
        '''تم ترجمة وثائق الرضاعة الطبيعية الخاصة بك إلى العربية:

تحتوي مجموعة وثائقك على معلومات شاملة حول الرضاعة الطبيعية ورعاية الرضع. تشمل المواضيع الرئيسية:

**1) فوائد الرضاعة الطبيعية**
- المزايا الصحية للأم والطفل
- الحماية المناعية والترابط العاطفي

**2) التقنيات الصحيحة**
- الالتقام الصحيح ووضعيات الرضاعة
- جداول الإرضاع والمدة المناسبة

**3) التحديات الشائعة**
- حلول لألم الحلمة والاحتقان
- إدارة قلة إدرار الحليب وارتباك الحلمة

**4) إنتاج الحليب**
- الهرمونات المشاركة في الإرضاع
- الطرق الطبيعية لزيادة إدرار الحليب

الوثائق تؤكد على الممارسات المبنية على الأدلة وتوصيات منظمة الصحة العالمية.''',
        name="example_assistant",
    ),

    # Example 5: Handling unavailable tools gracefully for breastfeeding queries
    HumanMessage(
        "Can you summarize my breastfeeding guides?", name="example_user"
    ),
    AIMessage(
        '''I apologize, but I don't have access to the summarization tool at the moment. However, I can help you by:

1. Using the knowledge base to get general information about breastfeeding topics
2. Answering specific questions about breastfeeding, milk supply, or infant care

Would you like me to help you with any specific breastfeeding questions or concerns?''',
        name="example_assistant",
    ),

    # Example 6: Permission-based tool access denial for breastfeeding translation
    HumanMessage(
        "Translate my breastfeeding guide to French", name="example_user"
    ),
    AIMessage(
        '''I don't have access to the translation tool for your account. Please contact your administrator to enable translation access.

In the meantime, I can help you with:
- Retrieving breastfeeding information from your knowledge base
- Finding specific guidance on latching, milk supply, or feeding schedules
- Answering questions about breastfeeding challenges and solutions

Is there anything specific about breastfeeding I can help you with?''',
        name="example_assistant",
    ),

    # Example 7: Using summarization with full access for breastfeeding content
    HumanMessage(
        "Give me a quick summary of my breastfeeding resources", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "get_summarization", "args": {}, "id": "call_5"}
        ],
    ),
    ToolMessage('''{"summary": "Your breastfeeding knowledge base contains essential guidance for nursing mothers, including: 1) Getting Started - Early initiation within first hour, skin-to-skin contact, and proper positioning. 2) Feeding Techniques - Correct latching, feeding frequency (8-12 times daily), and recognizing hunger cues. 3) Milk Supply Management - Natural ways to increase production, pumping and storage guidelines, and factors that affect supply. 4) Problem Solving - Solutions for engorgement, sore nipples, blocked ducts, and nipple confusion. 5) Health Benefits - Advantages for baby (immunity, nutrition, development) and mother (bonding, health protection, convenience).", "status": "success"}''', tool_call_id="call_5"),
    AIMessage(
        '''Here's a quick summary of your breastfeeding resources:

Your breastfeeding knowledge base contains essential guidance for nursing mothers, including:

**1) Getting Started**
- Early initiation within first hour after birth
- Skin-to-skin contact and proper positioning

**2) Feeding Techniques**
- Correct latching and feeding frequency (8-12 times daily)
- Recognizing hunger cues and feeding patterns

**3) Milk Supply Management**
- Natural ways to increase milk production
- Pumping and storage guidelines

**4) Problem Solving**
- Solutions for engorgement and sore nipples
- Managing blocked ducts and nipple confusion

**5) Health Benefits**
- Advantages for baby (immunity, nutrition, development)
- Benefits for mother (bonding, health protection, convenience)

These resources provide comprehensive support for successful breastfeeding.''',
        name="example_assistant",
    ),

    # Example 8: Arabic query about breastfeeding
    HumanMessage(
        "ما هي فوائد الرضاعة الطبيعية للأم؟", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "cag_knowledge_base", "args": {"user_query": "ما هي فوائد الرضاعة الطبيعية للأم؟"}, "id": "call_6"}
        ],
    ),
    ToolMessage('''فوائد الرضاعة الطبيعية للأم تشمل: تساعد على وقف النزيف بعد الولادة وعودة الرحم إلى حجمه الطبيعي، تقلل من مخاطر حدوث سرطان المبيض والثدي، تساعد الرضاعة المطلقة على تأخير حدوث الحمل خلال الستة أشهر الأولى، توفر للأم الراحة والوقت، وتساعد على إقامة علاقة حب وثيقة بين الأم ورضيعها.''', tool_call_id="call_6"),
    AIMessage(
        '''فوائد الرضاعة الطبيعية للأم تشمل:

**الفوائد الصحية:**
- تساعد على وقف النزيف بعد الولادة وعودة الرحم إلى حجمه الطبيعي
- تقلل من مخاطر حدوث سرطان المبيض والثدي لدى الأمهات

**تنظيم الأسرة:**
- تساعد الرضاعة المطلقة على تأخير حدوث الحمل خلال الستة أشهر الأولى

**الراحة والعملية:**
- توفر للأم الراحة والوقت اللذين تحتاج إليهما لرعاية طفلها ونفسها وأسرتها

**الترابط العاطفي:**
- تساعد على إقامة علاقة حب وثيقة بين الأم ورضيعها

هذه الفوائد تجعل الرضاعة الطبيعية مفيدة للأم والطفل على السواء.''',
        name="example_assistant",
    ),

    # Example 9: Combining multiple tools for breastfeeding content
    HumanMessage(
        "First summarize my breastfeeding guides, then translate the summary to Spanish", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "get_summarization", "args": {}, "id": "call_7"}
        ],
    ),
    ToolMessage('''{"summary": "Your breastfeeding guides cover essential topics for new mothers including proper latching techniques, feeding schedules, milk supply management, common challenges like engorgement and nipple pain, pumping and storage guidelines, weaning processes, and the introduction of solid foods at 6 months while continuing breastfeeding.", "status": "success"}''', tool_call_id="call_7"),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "get_translation", "args": {"target_language": "Spanish"}, "id": "call_8"}
        ],
    ),
    ToolMessage('''{"translation": "Sus guías de lactancia materna cubren temas esenciales para madres nuevas incluyendo técnicas de agarre adecuadas, horarios de alimentación, manejo del suministro de leche, desafíos comunes como congestión y dolor en los pezones, pautas de extracción y almacenamiento, procesos de destete, y la introducción de alimentos sólidos a los 6 meses mientras se continúa con la lactancia materna.", "target_language": "Spanish", "status": "success"}''', tool_call_id="call_8"),
    AIMessage(
        '''I've summarized your breastfeeding guides and translated them to Spanish:

**Summary:** Your breastfeeding guides cover essential topics for new mothers including proper latching techniques, feeding schedules, milk supply management, common challenges like engorgement and nipple pain, pumping and storage guidelines, weaning processes, and the introduction of solid foods at 6 months while continuing breastfeeding.

**Spanish Translation:** Sus guías de lactancia materna cubren temas esenciales para madres nuevas incluyendo técnicas de agarre adecuadas, horarios de alimentación, manejo del suministro de leche, desafíos comunes como congestión y dolor en los pezones, pautas de extracción y almacenamiento, procesos de destete, y la introducción de alimentos sólidos a los 6 meses mientras se continúa con la lactancia materna.''',
        name="example_assistant",
    )
]

