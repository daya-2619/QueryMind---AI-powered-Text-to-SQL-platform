import os
import sys
import logging
from typing import List, Dict, Any

# Adjust path to import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.services.schema_rag import schema_rag
from app.services.metadata_extractor import metadata_extractor
from app.services.query_validator import query_validator
from app.db.adapters import get_adapter
from app.services.llm import llm_service

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_pipeline")

# Predefined mock SQL dictionary for verification when API keys are not supplied
MOCK_SQL_MAP = {
    "show all customers from kolkata": {
        "sql": "SELECT customer_id, first_name, last_name, email, city FROM customers WHERE city = 'Kolkata';",
        "business_summary": "Fetches details of customers residing in Kolkata.",
        "technical_details": "Filters the customers table by matching the city column to 'Kolkata'.",
        "step_by_step": ["Query the customers table.", "Filter for rows where city is 'Kolkata'.", "Select id, name, and email fields."],
        "chart_recommendation": {"recommended": False, "chart_type": None, "x_axis_column": None, "y_axis_columns": [], "reasoning": "Not aggregated; simple list."}
    },
    "find the top 3 products with the highest price": {
        "sql": "SELECT product_id, product_name, category, price FROM products ORDER BY price DESC LIMIT 3;",
        "business_summary": "Retrieves the three most expensive products in stock.",
        "technical_details": "Sorts products by price in descending order and limits the result set to 3 rows.",
        "step_by_step": ["Query the products table.", "Sort the records in descending order of the price column.", "Limit output to 3 rows."],
        "chart_recommendation": {"recommended": True, "chart_type": "bar", "x_axis_column": "product_name", "y_axis_columns": ["price"], "reasoning": "Bar chart is perfect for comparing prices of distinct products."}
    },
    "count the total number of orders": {
        "sql": "SELECT COUNT(*) AS total_orders FROM orders;",
        "business_summary": "Calculates the grand total of all orders placed.",
        "technical_details": "Applies COUNT aggregation over all rows in the orders table.",
        "step_by_step": ["Query the orders table.", "Count the rows in the dataset."],
        "chart_recommendation": {"recommended": False, "chart_type": None, "x_axis_column": None, "y_axis_columns": [], "reasoning": "Single scalar output."}
    },
    "find customers who spent more than 500 dollars": {
        "sql": """SELECT c.customer_id, c.first_name, c.last_name, SUM(o.total_amount) AS total_spent 
FROM customers c 
JOIN orders o ON c.customer_id = o.customer_id 
GROUP BY c.customer_id, c.first_name, c.last_name 
HAVING SUM(o.total_amount) > 500 
ORDER BY total_spent DESC;""",
        "business_summary": "Identifies high-value customers who spent more than $500 in total across all orders.",
        "technical_details": "Joins customers and orders on customer_id, aggregates totals using SUM, groups by customer details, and filters using HAVING.",
        "step_by_step": ["Join customers table and orders table on customer_id.", "Group by customer identifier and names.", "Calculate total spending per customer using SUM.", "Filter grouped rows where SUM(total_amount) is greater than 500.", "Order in descending order of spend."],
        "chart_recommendation": {"recommended": True, "chart_type": "bar", "x_axis_column": "last_name", "y_axis_columns": ["total_spent"], "reasoning": "Bar chart illustrates total spending across high-value customers."}
    }
}

def print_table(columns: List[str], rows: List[Dict[str, Any]]):
    """Utility to print database results in clean format."""
    if not rows:
        print("Empty Result Set")
        return
        
    # Calculate widths
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            val_str = str(row.get(col, ""))
            widths[col] = max(widths[col], len(val_str))
            
    # Print header
    header = " | ".join(f"{col:<{widths[col]}}" for col in columns)
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    
    # Print rows
    for row in rows:
        line = " | ".join(f"{str(row.get(col, '')):<{widths[col]}}" for col in columns)
        print(line)
    print("-" * len(header))

def test_pipeline():
    logger.info("Starting Text-to-SQL Pipeline Verification Testing...")
    
    # Check target database configuration
    target_url = settings.TARGET_DATABASE_URL
    logger.info(f"Target DB URL: {target_url}")
    
    adapter = get_adapter(target_url)
    if not adapter.test_connection():
        logger.error("Target database is not accessible. Please run bootstrap_sample_db.py first.")
        sys.exit(1)
        
    logger.info("Target database connection verified successfully.")
    
    # Force rebuild vector index on schema metadata
    logger.info("Indexing schemas in Schema RAG Vector Database...")
    schema_rag.build_index(target_url)
    
    # Run test questions
    questions = [
        "Show all customers from Kolkata",
        "Find the top 3 products with the highest price",
        "Count the total number of orders",
        "Find customers who spent more than 500 dollars"
    ]
    
    has_api_keys = bool(settings.GEMINI_API_KEY or settings.OPENAI_API_KEY)
    
    if not has_api_keys:
        logger.warning("No Gemini or OpenAI API keys detected in settings. Using Mock LLM mode for translation verification.")
        
    for idx, question in enumerate(questions, 1):
        print(f"\n==================================================")
        print(f"TEST CASE {idx}: \"{question}\"")
        print(f"==================================================")
        
        # 1. Retrieve matching tables from RAG
        retrieved_tables = schema_rag.retrieve_relevant_schema(target_url, question, limit=3)
        retrieved_names = [t["name"] for t in retrieved_tables]
        print(f"1. Schema RAG Retrieved Tables: {', '.join(retrieved_names)}")
        
        # Format DDL
        schema_ddl = metadata_extractor.format_schema_for_prompt(retrieved_tables)
        
        # 2. Translate question to SQL
        logger.info("Executing translation via active SQL translation service...")
        result = llm_service.generate_sql_response(question, schema_ddl)
        generated_sql = result.get("sql")
        explanation = result.get("explanation", {})
        chart_rec = result.get("chart_recommendation", {})

        print(f"\n2. Generated SQL:\n{generated_sql}")
        
        # 3. Validate generated SQL
        sanitized_sql = query_validator.enforce_limit(generated_sql)
        is_safe, val_msg = query_validator.validate_sql(sanitized_sql)
        print(f"\n3. Security Validation: {'PASS' if is_safe else 'FAIL'} (Msg: {val_msg})")
        
        if not is_safe:
            continue
            
        # 4. Execute query
        print(f"\n4. Executing SQL on target database...")
        exec_result = adapter.execute_query(sanitized_sql)
        
        if exec_result["success"]:
            print(f"Query executed successfully in {exec_result['execution_time_ms']:.2f}ms. Rows returned: {exec_result['row_count']}")
            print("\nResult Set:")
            print_table(exec_result["columns"], exec_result["rows"])
        else:
            print(f"Query execution FAILED: {exec_result['error']}")
            
        # 5. Display business explanation
        print("\n5. SQL Explanation:")
        print(f"   * Business Summary: {explanation.get('business_summary')}")
        print(f"   * Technical Details: {explanation.get('technical_details')}")
        if explanation.get("step_by_step"):
            print("   * Step-by-step breakdown:")
            for s_idx, step in enumerate(explanation["step_by_step"], 1):
                print(f"     {s_idx}. {step}")
                
        # 6. Display chart recommendation
        print("\n6. Chart Recommendation:")
        if chart_rec.get("recommended"):
            print(f"   * Recommended: YES")
            print(f"   * Chart Type: {chart_rec.get('chart_type').upper()}")
            print(f"   * X-Axis: {chart_rec.get('x_axis_column')}")
            print(f"   * Y-Axis: {', '.join(chart_rec.get('y_axis_columns', []))}")
            print(f"   * Reasoning: {chart_rec.get('reasoning')}")
        else:
            print("   * Recommended: NO (Visualization not suitable for this query structure)")
            
    print("\n==================================================")
    print("Verification Testing Complete!")
    print("==================================================")

if __name__ == "__main__":
    test_pipeline()
