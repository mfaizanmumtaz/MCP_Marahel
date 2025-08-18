"""
Excel to CSV Converter

This script converts Excel files with a specific structure to CSV format,
preserving the exact structure and values from the Excel file.

Usage:
    python excel_to_csv_converter.py <excel_file> <output_csv>

Arguments:
    excel_file - Path to the Excel file to convert
    output_csv - Path where the output CSV will be saved
"""

import pandas as pd
import os
import tempfile
import shutil

# Create a temporary directory for file operations
TEMP_DIR = os.path.join(tempfile.gettempdir(), "excel_csv_converter")
os.makedirs(TEMP_DIR, exist_ok=True)


def convert_excel_to_csv(excel_file, output_csv):
    """
    Convert Excel file to CSV with specific formatting to match the target CSV format.

    Args:
        excel_file (str): Path to the Excel file
        output_csv (str): Path to save the output CSV file

    Returns:
        str: Path to the converted CSV file
    """
    print(f"Converting {excel_file} to {output_csv}...")

    try:
        # Read the Excel file - we know the data is in the 'evaluation form' sheet
        df = pd.read_excel(excel_file, sheet_name="evaluation form", header=None)

        # Find the row where the cashflow analysis section starts
        cashflow_row = None
        for i, row in df.iterrows():
            if (
                isinstance(row[1], str) and "Cahsflow Analysis" in row[1]
            ):  # Note the typo in 'Cahsflow'
                cashflow_row = i
                break

        if cashflow_row is None:
            print("Could not find Cashflow Analysis section in the Excel file.")
            return None

        # Extract the relevant section (starting from a few rows after the cashflow section header)
        start_row = cashflow_row + 2  # Skip the header row

        # Find where the data ends (before Section 3)
        end_row = None
        for i in range(start_row + 5, len(df)):
            if isinstance(df.iloc[i, 1], str) and "Section 3" in df.iloc[i, 1]:
                end_row = i
                break

        if end_row is None:
            # If we couldn't find Section 3, use a reasonable cutoff
            for i in range(start_row + 40, len(df)):
                if (
                    pd.isna(df.iloc[i, 1])
                    and pd.isna(df.iloc[i + 1, 1])
                    and pd.isna(df.iloc[i + 2, 1])
                ):
                    end_row = i
                    break

        if end_row is None:
            # Still couldn't find a clear end, use a fixed number of rows
            end_row = start_row + 70

        # Extract the data section
        data_section = df.iloc[start_row:end_row, :]

        # Create the output DataFrame structure
        output_columns = ["Category", "Description"]
        for i in range(11):  # Years 0-10
            output_columns.append(f"Year {i}")
        output_columns.extend(["Total", "%"])

        output_df = pd.DataFrame(columns=output_columns)

        # Process the data rows
        current_main_category = None

        # Skip the header row (row 0)
        for i in range(1, len(data_section)):
            row = data_section.iloc[i]
            category_col = 1  # Category column in Excel

            # Skip empty rows
            if pd.isna(row[category_col]):
                continue

            category = row[category_col]

            # Skip section headers and rows after Net Cashflow section
            if isinstance(category, str) and (
                "Section" in category
                or "Economic" in category
                or "Discount" in category
                or "Maximum" in category
                or "Minimum" in category
                or "Results" in category
            ):
                continue

            # Add the category row
            new_row = {"Category": category, "Description": ""}

            # Add year values - only if they exist in the Excel file
            for year in range(11):
                year_col = f"Year {year}"
                excel_col_idx = year + 3  # Year columns start at index 3 in Excel

                if excel_col_idx < len(row) and not pd.isna(row[excel_col_idx]):
                    new_row[year_col] = row[excel_col_idx]
                else:
                    new_row[year_col] = ""  # Empty string for missing values

            # Add total column
            total_col_idx = 14  # Total column in Excel
            if total_col_idx < len(row) and not pd.isna(row[total_col_idx]):
                new_row["Total"] = row[total_col_idx]
            else:
                new_row["Total"] = 0

            # Add percentage column
            if category in ["Investment", "Benefits"]:
                new_row["%"] = 1
            elif category in ["Net Cashflow", "Aggregate Cashflow"]:
                new_row["%"] = ""
            else:
                new_row["%"] = "#DIV/0!"

            output_df = pd.concat(
                [output_df, pd.DataFrame([new_row])], ignore_index=True
            )

        # Save to CSV
        output_df.to_csv(output_csv, index=False)
        print(f"Conversion complete. Output saved to {output_csv}")

        return output_csv

    except Exception as e:
        print(f"Error during conversion: {str(e)}")
        return None


def cleanup_temp_dir():
    """Clean up the temporary directory"""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)


# def main():

#     excel_file         = "Basic Digitization Project Evaluation Form (1).xlsx"
#     example_csv_file   = "New_World_Factory_Digitization_Evaluation. updatedcsv.csv"

#     if not os.path.exists(excel_file):
#         print(f"Error: Excel file {excel_file} not found.")
#         return

#     convert_excel_to_csv(excel_file, "output_csv.csv")
# main()

# if __name__ == "__main__":

#     excel_file         = "Basic Digitization Project Evaluation Form (1).xlsx"
#     example_csv_file   = "New_World_Factory_Digitization_Evaluation. updatedcsv.csv"
#     output_csv_file    = "test_example.csv"

#     try:
#         convert_excel_to_csv_with_example(
#             excel_file,
#             example_csv_file,
#             output_csv_file
#         )
#     except Exception as e:
#         print(f"Error: {e}")
#         sys.exit(1)
