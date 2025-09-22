import pandas as pd
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from config.settings import settings


def parse_evaluation_form(file_path):
    # Load the sheet without headers to preserve structure
    df = pd.read_excel(file_path, sheet_name=0, header=None)

    # Identify section header rows by looking for "Section" in the second column
    section_idxs = df[
        df.iloc[:, 1].astype(str).str.contains("Section", na=False)
    ].index.tolist()
    section_idxs.append(len(df))  # add end index for final section

    records = []
    # Iterate over each section
    for i in range(len(section_idxs) - 1):
        start = section_idxs[i]
        end = section_idxs[i + 1]
        section_name = df.iloc[start, 1]

        # Section 1: Key–Value pairs (Basic Information)
        if "Basic Information" in section_name:
            sub = df.iloc[start + 1 : end, :]
            # Rows where a field name appears in column 1
            field_rows = sub[sub.iloc[:, 1].notna()].index.tolist()
            for idx in field_rows:
                field = df.iloc[idx, 1]
                # Check for multi-line description
                if field == "Project Description":
                    # Aggregate all text in column 2 below this row until the next field
                    desc_lines = []
                    j = idx + 1
                    while j < end and pd.isna(df.iloc[j, 1]):
                        val = df.iloc[j, 2]
                        if pd.notna(val):
                            desc_lines.append(str(val))
                        j += 1
                    value = " ".join(desc_lines)
                else:
                    # Single-line response: any non-null in columns 2+
                    vals = df.iloc[idx, 2:].dropna().astype(str).tolist()
                    value = " ".join(vals) if vals else None
                records.append(
                    {"Section": section_name, "Field": field, "Value": value}
                )

        # Section 2: Cashflow Analysis (table)
        elif "Cahsflow" in section_name or "Cashflow" in section_name:
            sub = df.iloc[start + 1 : end, :]
            # Find header row by looking for "Category"
            header_idx = sub[sub.iloc[:, 1] == "Category"].index[0]
            headers = df.iloc[header_idx, 1:16].tolist()
            # Iterate data rows until next blank Category
            for idx in range(header_idx + 1, end):
                category = df.iloc[idx, 1]
                if pd.isna(category):
                    continue
                row_vals = df.iloc[idx, 1:16].tolist()
                rec = {"Section": section_name}
                for col_name, val in zip(headers, row_vals):
                    rec[col_name] = val
                records.append(rec)

        # Section 3: Impact Analysis and Recommendations
        elif "Impact Analysis" in section_name:
            sub = df.iloc[start + 1 : end, :]
            # Find header row by sub-section titles
            header_idx = sub[
                sub.iloc[:, 1].str.contains("Economic Basis", na=False)
            ].index[0]
            # Economic Basis and Assumptions (left block)
            for idx in range(header_idx + 1, end):
                field = df.iloc[idx, 1]
                if pd.notna(field):
                    value = df.iloc[idx, 2]
                    records.append(
                        {
                            "Section": section_name,
                            "Block": "Economic Basis and Assumptions",
                            "Metric": field,
                            "Value": value,
                        }
                    )
            # Key Financials (right block)
            for idx in range(header_idx + 1, end):
                metric = df.iloc[idx, 4]
                if pd.notna(metric):
                    val = df.iloc[idx, 6]
                    unit = df.iloc[idx, 7] if df.shape[1] > 7 else None
                    records.append(
                        {
                            "Section": section_name,
                            "Block": "Key Financials",
                            "Metric": metric,
                            "Value": val,
                            "Unit": unit,
                        }
                    )

    return pd.DataFrame(records)


def query_dataframe_with_openai(
    df: pd.DataFrame,
    query: str,
    model: str = "gpt-4.1-mini",
    temperature: float = 0.0,
) -> str:
    """
    Serialize the DataFrame to CSV, embed it in a prompt along with the user's query,
    call the OpenAI ChatCompletion API, and return the assistant's reply.
    """
    # 1. Convert DataFrame to CSV (or JSON if you prefer)
    csv_data = df.to_csv(index=False)

    # 2. Build the chat messages
    # system_msg = {
    #     "role": "system",
    #     "content": "You are a helpful data assistant. "
    #                "I will give you a table in CSV format and then ask a question about it.",
    # }
    # user_msg = {
    #     "role": "user",
    #     "content": f"Here is the data in CSV form:\n\n{csv_data}\n\n"
    #                f"Question: {query}"
    # }

    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful data assistant. "
                "I will give you a table in CSV format and then ask a question about it.",
            ),
            (
                "user",
                "Here is the data in CSV form:\n\n{csv_data}\n\nQuestion: {query}",
            ),
        ]
    )

    # 3. Call the OpenAI API
    # resp = client.responses.create(
    #     model=model,
    #     input=[system_msg, user_msg],
    #     temperature=temperature,
    # )
    chain = template | ChatOpenAI(model=model, temperature=temperature)
    # 4. Extract and return the assistant's answer
    return chain.invoke({"csv_data": csv_data, "query": query}).content


# Example usage
# file_path = 'experiments/New_World_Factory_Digitization_Evaluation.xlsx'
# df_records = parse_evaluation_form(file_path)

# query = 'what is the net cashflow for the year 0'
# query = 'what is the amount of inventments in year 0'
# query = 'what is the sum cashflow for all years'
# query = 'كم كانت قيمة الاسثمار في السنة الأولى'
# query = 'كم نسبة العائد من الاستثمار وفقا للبيانات المرفوعة'
# query = 'ما هو الاستثمار لجميع السنوات؟'
# query = 'ما هو العائد من الاستثمار في السنة الأولى'
# query = 'What is the ROI on year 1'
# query = 'كم العائد من الاستثمار'
# query = 'what is the Payback Period'
# query = 'ما هي فترة الاسترداد'
# query = 'ما هو التقيم العام للمصنع'
# query = 'ما الذي يجب علينا فعله لزيادة نسبة العائد من الاستثمار خلال الخمس السنوات القادمة'
# query = "what is the investment of year zero and the avg of the year zero"
# answer = query_dataframe_with_openai(df_records, query)

# print('QUERY: ', query)
# print('ANSWER: ', answer)
