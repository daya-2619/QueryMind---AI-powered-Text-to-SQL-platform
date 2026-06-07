import json
import logging
from typing import Dict, List, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# System instructions directing the model's behavior and formatting rules
SQL_GENERATION_SYSTEM_PROMPT = """You are an expert Enterprise Text-to-SQL AI Assistant and Database Analyst.
Your task is to convert a natural language question into a syntactically correct SQL query for the target database schema, provide a step-by-step business explanation, and suggest an optimal chart visualization.

Return your response EXACTLY as a JSON object with this schema:
{
  "sql": "The raw generated SQL query string",
  "explanation": {
    "business_summary": "A summary of what this query calculates in simple business language.",
    "technical_details": "Details on tables joined, filters applied, grouping, or aggregates.",
    "step_by_step": [
      "Step 1 details...",
      "Step 2 details..."
    ]
  },
  "chart_recommendation": {
    "recommended": true or false,
    "chart_type": "bar" or "line" or "pie" or "area" or "scatter" or null,
    "x_axis_column": "The column name to use for the X-axis (independent variable)",
    "y_axis_columns": ["The column name(s) to use for the Y-axis (values)"],
    "reasoning": "Brief explanation for why this chart type is suitable"
  }
}

Guidelines for SQL Generation:
1. ONLY write SELECT statements. Reject any requests attempting DROP, DELETE, UPDATE, INSERT, ALTER, or TRUNCATE.
2. Use the provided database schema (DDL-like context) to identify correct tables and columns.
3. Be careful with joins: use the correct FOREIGN KEY relationships documented in the schema.
4. Handle column reference ambiguity by always prefixing columns with their table name or alias (e.g., c.customer_id instead of customer_id).
5. Always apply a limit to the results to prevent loading too much data. If no limit is implied, enforce a standard limit of 1000 rows (e.g., LIMIT 1000).
6. Target Dialect: The target database uses standard SQL (PostgreSQL/SQLite compatible). Avoid database-specific quirks unless necessary.
7. Maintain Conversational Context: If a session history is provided, verify if the user's current question is a follow-up to previous queries (e.g., "only from Kolkata" is a filter on the previous query). If so, adapt the previous SQL accordingly.

Example Question: "Compare monthly revenue for the last 12 months"
Expected JSON Response Structure:
{
  "sql": "SELECT DATE_TRUNC('month', order_date) as month, SUM(total_amount) as revenue FROM orders GROUP BY 1 ORDER BY 1 DESC LIMIT 12;",
  "explanation": {
    "business_summary": "This query calculates the total revenue generated in each of the last 12 months.",
    "technical_details": "It aggregates order totals using SUM, groups them by month using DATE_TRUNC, and sorts chronologically.",
    "step_by_step": [
      "Truncate the order date to the month level.",
      "Aggregate the total amount of orders per month.",
      "Sort the results by month in descending order.",
      "Limit the output to the last 12 months."
    ]
  },
  "chart_recommendation": {
    "recommended": true,
    "chart_type": "line",
    "x_axis_column": "month",
    "y_axis_columns": ["revenue"],
    "reasoning": "A line chart is ideal for visualizing trends and change in revenue over time."
  }
}
"""

class LLMService:
    """Service to handle conversions from natural language to SQL + explanations + visualizations."""



    def _generate_local_sql(
        self,
        question: str,
        schema_ddl: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        connection_url: Optional[str] = None
    ) -> Dict[str, Any]:
        import re
        q_lower = question.lower()
        
        # Determine dialect from connection settings
        target_url = connection_url or settings.TARGET_DATABASE_URL
        dialect = "sqlite" if "sqlite" in target_url.lower() else "postgresql"
        
        # Comparison operators dictionary for parsing numeric constraints
        operators_map = {
            r'(?:greater than|more than|above|over|exceeding|>|\bgt\b)': '>',
            r'(?:less than|lower than|under|below|<|\blt\b)': '<',
            r'(?:at least|minimum|from|>=|\bgeq\b)': '>=',
            r'(?:at most|maximum|up to|<=|\bleq\b)': '<=',
            r'(?:equal to|equals|is|exactly|=)': '=',
            r'(?:not equal|is not|!=)': '!='
        }
        
        # 1. Helper function for fuzzy string matching (Jaccard similarity of 2-grams)
        def fuzzy_score(s1, s2):
            s1, s2 = s1.lower(), s2.lower()
            if s1 == s2:
                return 1.0
            # Split tokens by underscore or space
            tokens1 = re.split(r'[_ ]', s1)
            tokens2 = re.split(r'[_ ]', s2)
            for t1 in tokens1:
                if t1 in tokens2:
                    return 0.8
                for t2 in tokens2:
                    if t1 == t2:
                        return 0.8
            g1 = set(s1[i:i+2] for i in range(len(s1)-1))
            g2 = set(s2[i:i+2] for i in range(len(s2)-1))
            if not g1 or not g2:
                return 0.0
            return len(g1.intersection(g2)) / len(g1.union(g2))

        # Helper for plural to singular conversion
        def singular(name):
            name = name.lower()
            if name.endswith("ies"):
                return name[:-3] + "y"
            if name.endswith("s") and not name.endswith("ss"):
                return name[:-1]
            return name

        # Helper to extract date filters
        def extract_date_filters(q_str, tables_cols, col_types, active_tables, db_dialect, primary_tbl=None):
            filters = []
            q_low = q_str.lower()
            date_col_ref = None
            date_tbl = None
            
            # Order search tables so primary table is checked first
            search_tables = []
            if primary_tbl and primary_tbl in active_tables:
                search_tables.append(primary_tbl)
            for tbl in active_tables:
                if tbl not in search_tables:
                    search_tables.append(tbl)
                    
            for tbl in search_tables:
                for col in tables_cols[tbl]:
                    col_type = col_types.get(f"{tbl}.{col}", "")
                    if "date" in col or "time" in col or col_type in ("TIMESTAMP", "DATE", "DATETIME"):
                        date_col_ref = f"{tbl}.{col}" if len(active_tables) > 1 else col
                        date_tbl = tbl
                        break
                if date_col_ref:
                    break
            
            if not date_col_ref:
                for tbl in tables_cols:
                    for col in tables_cols[tbl]:
                        col_type = col_types.get(f"{tbl}.{col}", "")
                        if "date" in col or "time" in col or col_type in ("TIMESTAMP", "DATE", "DATETIME"):
                            date_col_ref = f"{tbl}.{col}"
                            date_tbl = tbl
                            break
                    if date_col_ref:
                        break
                        
            if not date_col_ref:
                return filters
            
            clause = None
            days_match = re.search(r"last\s+(\d+)\s+days", q_low)
            months_match = re.search(r"last\s+(\d+)\s+months", q_low)
            year_match = re.search(r"last\s+year", q_low)
            if days_match:
                days = days_match.group(1)
                if db_dialect == "sqlite":
                    clause = f"{date_col_ref} >= datetime('now', '-{days} days')"
                else:
                    clause = f"{date_col_ref} >= CURRENT_DATE - INTERVAL '{days} days'"
            elif months_match:
                months = months_match.group(1)
                if db_dialect == "sqlite":
                    clause = f"{date_col_ref} >= datetime('now', '-{months} months')"
                else:
                    clause = f"{date_col_ref} >= CURRENT_DATE - INTERVAL '{months} months'"
            elif year_match:
                if db_dialect == "sqlite":
                    clause = f"{date_col_ref} >= datetime('now', '-1 year')"
                else:
                    clause = f"{date_col_ref} >= CURRENT_DATE - INTERVAL '1 year'"
            
            date_iso_match = re.search(r"(?:since|after|from)\s+(\d{4}-\d{2}-\d{2})", q_low)
            if date_iso_match:
                date_str = date_iso_match.group(1)
                clause = f"{date_col_ref} >= '{date_str}'"
            date_before_match = re.search(r"before\s+(\d{4}-\d{2}-\d{2})", q_low)
            if date_before_match:
                date_str = date_before_match.group(1)
                clause = f"{date_col_ref} <= '{date_str}'"
            year_num_match = re.search(r"\bin\s+(\d{4})\b", q_low)
            if year_num_match:
                year = year_num_match.group(1)
                if db_dialect == "sqlite":
                    clause = f"strftime('%Y', {date_col_ref}) = '{year}'"
                else:
                    clause = f"EXTRACT(YEAR FROM {date_col_ref}) = {year}"
            
            if clause:
                filters.append({"clause": clause, "table": date_tbl})
            return filters

        # Helper to extract select columns explicitly requested
        def extract_additional_select_items(q_str, tables_cols, active_tables):
            additional = []
            q_low = q_str.lower()
            if any(w in q_low for w in ("show", "select", "display", "get", "list", "emails", "names")):
                for tbl in active_tables:
                    for col in tables_cols[tbl]:
                        if col in q_low or col.replace('_', ' ') in q_low:
                            col_ref = f"{tbl}.{col}" if len(active_tables) > 1 else col
                            additional.append(col_ref)
            return additional

        # Helper to extract sorting from question
        def extract_sorting(q_str, tables_cols, active_tables):
            q_low = q_str.lower()
            if "sort" in q_low or "order" in q_low or "rank" in q_low:
                direction = "DESC" if any(w in q_low for w in ("desc", "highest", "most", "expensive", "largest", "top")) else "ASC"
                best_col = None
                best_tbl = None
                best_score = 0.0
                for tbl in active_tables:
                    for col in tables_cols[tbl]:
                        score = 0.0
                        if col in q_low:
                            score += 2.0
                        for cw in col.split('_'):
                            if cw in q_low:
                                score += 1.0
                        if score > best_score:
                            best_score = score
                            best_col = col
                            best_tbl = tbl
                if best_col:
                    col_ref = f"{best_tbl}.{best_col}" if len(active_tables) > 1 else best_col
                    return f"{col_ref} {direction}"
            return None

        # Helper to extract limit
        def extract_limit(q_str):
            limit_match = re.search(r"(?:limit|top)\s+(\d+)", q_str.lower())
            if limit_match:
                return int(limit_match.group(1))
            return None

        # 2. Parse DDL to get tables, columns, types, and foreign keys
        tables = {}
        col_types = {}
        relations = {}
        
        for table_match in re.finditer(r"CREATE TABLE (\w+)\s*\((.*?)\);", schema_ddl, re.DOTALL | re.IGNORECASE):
            table_name = table_match.group(1).lower()
            columns_str = table_match.group(2)
            cols = []
            relations[table_name] = {}
            for col_line in columns_str.split("\n"):
                col_line = col_line.strip().strip(",")
                if not col_line:
                    continue
                # Parse FK constraints
                fk_match = re.search(r"FOREIGN KEY\s*\((.*?)\)\s*REFERENCES\s*(\w+)\s*\((.*?)\)", col_line, re.IGNORECASE)
                if fk_match:
                    local_col = fk_match.group(1).strip().lower()
                    ref_table = fk_match.group(2).strip().lower()
                    ref_col = fk_match.group(3).strip().lower()
                    relations[table_name][local_col] = (ref_table, ref_col)
                    continue

                # Parse inline REFERENCES constraints
                inline_fk_match = re.search(r"^\s*(\w+)\s+.*?\s+REFERENCES\s+(\w+)\s*\((.*?)\)", col_line, re.IGNORECASE)
                if inline_fk_match:
                    local_col = inline_fk_match.group(1).strip().lower()
                    if local_col not in ("foreign", "primary", "unique", "constraint"):
                        ref_table = inline_fk_match.group(2).strip().lower()
                        ref_col = inline_fk_match.group(3).strip().lower()
                        relations[table_name][local_col] = (ref_table, ref_col)
                
                if col_line.startswith("PRIMARY KEY") or col_line.startswith("UNIQUE") or col_line.startswith("CONSTRAINT"):
                    continue
                    
                parts = col_line.split()
                if parts:
                    col_name = parts[0].strip().replace('"', '').replace('`', '').lower()
                    if col_name in ("primary", "foreign", "unique", "constraint"):
                        continue
                    col_type = parts[1].strip().upper() if len(parts) > 1 else "TEXT"
                    cols.append(col_name)
                    col_types[f"{table_name}.{col_name}"] = col_type
            tables[table_name] = cols

        if not tables:
            # Fallback
            return {
                "sql": "SELECT * FROM sqlite_master;",
                "explanation": {"business_summary": "Fallback schema check.", "technical_details": "", "step_by_step": []},
                "chart_recommendation": {"recommended": False, "chart_type": None, "x_axis_column": None, "y_axis_columns": [], "reasoning": None}
            }

        # 3. Build Bidirectional Join relation graph
        graph = {t: {} for t in tables}
        for tbl in relations:
            for local_col, (ref_tbl, ref_col) in relations[tbl].items():
                if tbl in graph and ref_tbl in tables:
                    graph[tbl][ref_tbl] = (local_col, ref_col)
                    graph[ref_tbl][tbl] = (ref_col, local_col)

        # 4. BFS Join Path Resolver
        def bfs_path(start, end):
            queue = [[start]]
            visited = {start}
            while queue:
                path = queue.pop(0)
                node = path[-1]
                if node == end:
                    return path
                for neighbor in graph.get(node, {}):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(path + [neighbor])
            return None

        # Build join links for a set of tables
        def resolve_joins(tables_to_join, primary_tbl):
            joins = []
            visited_joins = set()
            connected_tables = {primary_tbl}
            for t in tables_to_join:
                if t == primary_tbl or t in connected_tables:
                    continue
                path = bfs_path(primary_tbl, t)
                if path:
                    for i in range(len(path)-1):
                        t1, t2 = path[i], path[i+1]
                        if (t1, t2) not in visited_joins and (t2, t1) not in visited_joins:
                            col1, col2 = graph[t1][t2]
                            joins.append(f" JOIN {t2} ON {t1}.{col1} = {t2}.{col2}")
                            visited_joins.add((t1, t2))
                            connected_tables.add(t2)
            return joins, list(connected_tables)

        # Helper to parse previous SQL components
        def parse_sql_components(sql):
            sql_clean = sql.strip().rstrip(';').replace('\n', ' ')
            sql_clean = re.sub(r'\s+', ' ', sql_clean)
            sql_upper = sql_clean.upper()
            
            keywords = ["SELECT ", "FROM ", "WHERE ", "GROUP BY ", "HAVING ", "ORDER BY ", "LIMIT "]
            kw_pos = {}
            idx = 0
            while idx < len(sql_clean):
                found_kw = None
                best_pos = len(sql_clean)
                for kw in keywords:
                    match = re.search(r'\b' + kw.strip() + r'\b', sql_upper[idx:])
                    if match:
                        pos = idx + match.start()
                        if pos < best_pos:
                            best_pos = pos
                            found_kw = kw.strip()
                if found_kw:
                    kw_pos[found_kw] = best_pos
                    idx = best_pos + len(found_kw)
                else:
                    break
            
            sorted_kws = sorted(kw_pos.items(), key=lambda x: x[1])
            components = {}
            for i, (kw, pos) in enumerate(sorted_kws):
                start = pos + len(kw) + 1
                end = sorted_kws[i+1][1] if i + 1 < len(sorted_kws) else len(sql_clean)
                components[kw] = sql_clean[start:end].strip()
            return components

        # 5. Check if this is a follow-up query to merge conversational context
        previous_sql = None
        if chat_history:
            for msg in reversed(chat_history):
                content = msg.get("content", "")
                if msg.get("role") == "assistant" and "Generated SQL:" in content:
                    sql_str = content.replace("Generated SQL:", "").strip()
                    if sql_str.endswith('.'):
                        sql_str = sql_str[:-1].strip()
                    previous_sql = sql_str
                    break

        # Check follow-up status
        is_follow_up = False
        if previous_sql:
            follow_up_keywords = ["only", "where", "filter", "sort", "order", "limit", "top", "grouped", "group", "by", "show", "also", "and"]
            words_q = re.findall(r"\w+", q_lower)
            if words_q and words_q[0] in follow_up_keywords:
                is_follow_up = True
            else:
                matched_tables_new = set()
                for t in tables:
                    t_sing = singular(t)
                    if t in q_lower or t_sing in q_lower:
                        matched_tables_new.add(t)
                if not matched_tables_new:
                    is_follow_up = True

        if is_follow_up and previous_sql:
            logger.info(f"Merging follow-up question context with previous SQL: {previous_sql}")
            try:
                prev_comp = parse_sql_components(previous_sql)
                
                prev_from = prev_comp.get("FROM", "")
                active_tables = []
                for t in tables:
                    if re.search(r'\b' + t + r'\b', prev_from.lower()):
                        active_tables.append(t)
                if not active_tables and tables:
                    active_tables = [list(tables.keys())[0]]
                primary_table = active_tables[0]
                
                new_filters = []
                
                # Numeric filters
                cleaned_q = re.sub(r'\b(top|limit|page)\s+\d+', '', q_lower)
                numbers = re.findall(r'\b\d+(?:\.\d+)?\b', cleaned_q)
                
                for num in numbers:
                    pos = cleaned_q.find(num)
                    start_idx = max(0, pos - 45)
                    context = cleaned_q[start_idx:pos]
                    op = '='
                    for regex, symbol in operators_map.items():
                        if re.search(regex, context):
                            op = symbol
                            break
                    best_col = None
                    best_tbl = None
                    best_score = 0.0
                    for tbl in active_tables:
                        for col in tables[tbl]:
                            col_type = col_types.get(f"{tbl}.{col}", "")
                            if not any(typ in col_type for typ in ("INT", "DECIMAL", "FLOAT", "DOUBLE", "NUMERIC", "PRICE", "AMOUNT", "QUANTITY", "RATING")):
                                continue
                            score = fuzzy_score(col, context) + (1.0 if any(cw in context for cw in col.split('_')) else 0.0)
                            if col in column_synonyms:
                                if any(syn in context or syn in q_lower for syn in column_synonyms[col]):
                                    score += 1.5
                            if col.endswith("_id") and "id" not in context and "id" not in q_lower:
                                score -= 2.0
                            if score > best_score:
                                best_score = score
                                best_col = col
                                best_tbl = tbl
                    if not best_col:
                        for tbl in active_tables:
                            for col in tables[tbl]:
                                if any(typ in col_types.get(f"{tbl}.{col}", "") for typ in ("INT", "DECIMAL", "FLOAT", "DOUBLE", "NUMERIC")):
                                    best_col, best_tbl = col, tbl
                                    break
                            if best_col:
                                break
                    if best_col:
                        col_ref = f"{best_tbl}.{best_col}" if len(active_tables) > 1 else best_col
                        is_agg = "spent" in cleaned_q or "total" in cleaned_q or "sum" in cleaned_q or "having" in cleaned_q
                        new_filters.append({"ref": col_ref, "op": op, "val": num, "is_agg": is_agg, "table": best_tbl})

                # Text/Categorical filters
                cities = ["kolkata", "mumbai", "delhi", "bengaluru", "chennai", "new york", "london", "tokyo"]
                countries = ["india", "usa", "uk", "japan"]
                categories = ["electronics", "clothing", "home & kitchen", "home", "kitchen", "books", "sports"]
                statuses = ["completed", "pending", "cancelled", "processing", "shipped"]
                
                for c in cities:
                    if c in q_lower:
                        tbl = "customers"
                        col_ref = f"{tbl}.city"
                        new_filters.append({"ref": col_ref, "op": "=", "val": f"'{c.title()}'", "is_agg": False, "table": tbl})
                for c in countries:
                    if c in q_lower:
                        tbl = "customers"
                        col_ref = f"{tbl}.country"
                        val = "USA" if c == "usa" else ("UK" if c == "uk" else c.title())
                        new_filters.append({"ref": col_ref, "op": "=", "val": f"'{val}'", "is_agg": False, "table": tbl})
                for c in categories:
                    if c in q_lower:
                        tbl = "products"
                        col_ref = f"{tbl}.category"
                        mapped_cat = "Home & Kitchen" if c in ("home", "kitchen", "home & kitchen") else c.title()
                        new_filters.append({"ref": col_ref, "op": "=", "val": f"'{mapped_cat}'", "is_agg": False, "table": tbl})
                for s in statuses:
                    if s in q_lower:
                        tbl = "orders"
                        col_ref = f"{tbl}.status"
                        new_filters.append({"ref": col_ref, "op": "=", "val": f"'{s.capitalize()}'", "is_agg": False, "table": tbl})
                
                # Quoted string literals
                quoted = re.findall(r"['\"](.*?)['\"]", question)
                for q_val in quoted:
                    pos = question.find(q_val)
                    context = question[max(0, pos-20):pos].lower()
                    best_col = None
                    best_tbl = None
                    best_score = 0.0
                    for tbl in tables:
                        for col in tables[tbl]:
                            if col in ("email", "first_name", "last_name", "product_name", "category", "status", "city"):
                                score = 1.0 if col in context else 0.0
                                if score > best_score:
                                    best_score = score
                                    best_col = col
                                    best_tbl = tbl
                    if not best_col:
                        best_tbl = "products" if "products" in active_tables else ("customers" if "customers" in active_tables else primary_table)
                        best_col = "product_name" if best_tbl == "products" else ("first_name" if best_tbl == "customers" else tables[best_tbl][0])
                    col_ref = f"{best_tbl}.{best_col}"
                    op = "LIKE" if "name" in best_col or "text" in best_col else "="
                    val = f"'%{q_val}%'" if op == "LIKE" else f"'{q_val}'"
                    new_filters.append({"ref": col_ref, "op": op, "val": val, "is_agg": False, "table": best_tbl})
                    
                date_filters = extract_date_filters(question, tables, col_types, active_tables, dialect, primary_table)
                for df in date_filters:
                    new_filters.append({"custom_clause": df["clause"], "is_agg": False, "table": df["table"]})

                # Check if we need to dynamically join new tables for the filters
                tables_changed = False
                for f in new_filters:
                    f_tbl = f.get("table")
                    if f_tbl and f_tbl not in active_tables:
                        active_tables.append(f_tbl)
                        tables_changed = True
                        
                if tables_changed:
                    new_joins, _ = resolve_joins(active_tables, primary_table)
                    prev_from = f"{primary_table}{''.join(new_joins)}"

                where_clauses = [prev_comp["WHERE"]] if "WHERE" in prev_comp else []
                having_clauses = [prev_comp["HAVING"]] if "HAVING" in prev_comp else []
                
                for f in new_filters:
                    if "custom_clause" in f:
                        where_clauses.append(f["custom_clause"])
                    else:
                        clause = f"{f['ref']} {f['op']} {f['val']}"
                        if f["is_agg"]:
                            having_clauses.append(clause)
                        else:
                            where_clauses.append(clause)
                            
                select_clause = prev_comp.get("SELECT", "*")
                add_select = extract_additional_select_items(question, tables, active_tables)
                for col_item in add_select:
                    if col_item not in select_clause:
                        select_clause += f", {col_item}"
                        
                order_clause = prev_comp.get("ORDER BY")
                new_order = extract_sorting(question, tables, active_tables)
                if new_order:
                    order_clause = new_order
                    
                limit_val = prev_comp.get("LIMIT", "1000")
                new_limit = extract_limit(question)
                if new_limit:
                    limit_val = str(new_limit)

                sql_parts = [f"SELECT {select_clause} FROM {prev_from}"]
                if where_clauses:
                    sql_parts.append(" WHERE " + " AND ".join(f"({w})" for w in where_clauses))
                if "GROUP BY" in prev_comp:
                    sql_parts.append(f" GROUP BY {prev_comp['GROUP BY']}")
                if having_clauses:
                    sql_parts.append(" HAVING " + " AND ".join(f"({h})" for h in having_clauses))
                if order_clause:
                    sql_parts.append(f" ORDER BY {order_clause}")
                sql_parts.append(f" LIMIT {limit_val};")
                
                final_sql = "".join(sql_parts)
                
                return {
                    "sql": final_sql,
                    "explanation": {
                        "business_summary": f"Refinement of previous query: '{question}' using conversation context.",
                        "technical_details": f"Appended constraints or sorting on top of previous query structure.",
                        "step_by_step": ["Identified query context as conversational follow-up.", "Merged constraints into previous statement."]
                    },
                    "chart_recommendation": {
                        "recommended": "GROUP BY" in prev_comp,
                        "chart_type": "bar" if "GROUP BY" in prev_comp else None,
                        "x_axis_column": None,
                        "y_axis_columns": [],
                        "reasoning": "Maintained previous query format."
                    }
                }
            except Exception as e:
                logger.error(f"Failed to merge follow-up SQL, compiling from scratch: {e}")

        # 6. Synonym mappings for target tables and columns in our schema
        table_synonyms = {
            "customers": ["customer", "client", "clients", "user", "users", "buyer", "buyers", "who", "signup", "joined"],
            "products": ["product", "item", "items", "good", "goods", "merchandise"],
            "orders": ["order", "purchase", "purchased", "sale", "sales", "transaction", "transactions", "spent", "spend"],
            "order_items": ["item", "items", "quantity", "qty"],
            "reviews": ["review", "reviews", "rating", "ratings", "feedback", "stars"]
        }
        
        column_synonyms = {
            "total_amount": ["spent", "spend", "revenue", "sales", "total", "amount", "value", "price"],
            "price": ["cost", "charge", "value", "price", "expensive", "cheapest"],
            "stock_quantity": ["stock", "quantity", "qty", "inventory", "available"],
            "rating": ["stars", "rating", "score", "reviews"],
            "created_at": ["signup", "joined", "registered", "created"],
            "order_date": ["date", "time", "when", "ordered", "purchased"]
        }

        words = re.findall(r"\w+", q_lower)
        required_tables = set()
        matched_cols_by_table = {t: [] for t in tables}
        
        for word in words:
            for t in tables:
                t_sing = singular(t)
                is_match = fuzzy_score(word, t) > 0.7 or fuzzy_score(word, t_sing) > 0.7
                if not is_match and t in table_synonyms:
                    is_match = any(fuzzy_score(word, syn) > 0.8 for syn in table_synonyms[t])
                if is_match:
                    required_tables.add(t)
            exact_cols = []
            for t in tables:
                for col in tables[t]:
                    if word == col or word == col.replace('_', ''):
                        exact_cols.append((t, col))
            
            if exact_cols:
                for t, col in exact_cols:
                    matched_cols_by_table[t].append(col)
                    if not col.endswith("_id") or "id" in word or col in q_lower:
                        required_tables.add(t)
            else:
                for t in tables:
                    for col in tables[t]:
                        is_col_match = fuzzy_score(word, col) > 0.7 or any(fuzzy_score(word, cw) > 0.7 for cw in col.split('_'))
                        if not is_col_match and col in column_synonyms:
                            is_col_match = any(fuzzy_score(word, syn) > 0.8 for syn in column_synonyms[col])
                        if is_col_match:
                            matched_cols_by_table[t].append(col)
                            if not col.endswith("_id") or "id" in word or col in q_lower:
                                required_tables.add(t)

        if not required_tables:
            primary_table = max(tables, key=lambda t: len(matched_cols_by_table[t]))
            required_tables.add(primary_table)
        else:
            table_scores = {}
            for t in required_tables:
                score = 10 if t in q_lower else 0
                score += len(matched_cols_by_table[t]) * 2
                table_scores[t] = score
            primary_table = max(table_scores, key=table_scores.get)

        joins, connected_tables = resolve_joins(required_tables, primary_table)

        # 7. Identify aggregates
        select_items = []
        aggregates_list = []
        
        agg_keywords = {
            "COUNT": ["count", "number of", "how many", "quantity of", "total orders", "total number of"],
            "AVG": ["average", "avg", "mean"],
            "SUM": ["sum", "total amount", "total spend", "total revenue", "total sales", "spent", "revenue", "sales", "total"],
            "MAX": ["maximum", "max", "highest", "most", "largest", "expensive"],
            "MIN": ["minimum", "min", "lowest", "least", "cheapest"]
        }

        numeric_cols_meta = []
        for t in connected_tables:
            for col in tables[t]:
                col_type = col_types.get(f"{t}.{col}", "")
                if any(typ in col_type for typ in ("INT", "DECIMAL", "FLOAT", "DOUBLE", "NUMERIC", "PRICE", "AMOUNT", "QUANTITY", "RATING")):
                    numeric_cols_meta.append((t, col))

        has_limit_keyword = any(w in q_lower for w in ("top", "limit", "first", "last"))
        has_and_keyword = any(w in q_lower for w in ("and", "&", "plus"))
        
        for agg_fn, kws in agg_keywords.items():
            if has_limit_keyword and agg_fn in ("MAX", "MIN"):
                continue
            matched_agg = False
            for kw in kws:
                if kw in q_lower:
                    kw_pos = q_lower.find(kw)
                    context_q = q_lower[kw_pos:kw_pos+30]
                    best_match_col = None
                    best_tbl = None
                    best_score = 0.0
                    for t, col in numeric_cols_meta:
                        score = fuzzy_score(col, context_q) + (1.0 if any(cw in context_q for cw in col.split('_')) else 0.0)
                        if col in column_synonyms:
                            if any(syn in context_q or syn in q_lower for syn in column_synonyms[col]):
                                score += 1.5
                        if score > best_score:
                            best_score = score
                            best_match_col = col
                            best_tbl = t
                            
                    if not best_match_col and agg_fn != "COUNT":
                        # 1. Match using synonyms or exact/subwords of non-id columns
                        for t, col in numeric_cols_meta:
                            if col.endswith("_id"):
                                continue
                            is_col_match = col in q_lower or any(cw in q_lower for cw in col.split('_'))
                            if not is_col_match and col in column_synonyms:
                                is_col_match = any(syn in q_lower for syn in column_synonyms[col])
                            if is_col_match:
                                best_match_col, best_tbl = col, t
                                break
                                
                        # 2. Match using synonyms or exact/subwords of any columns (including id)
                        if not best_match_col:
                            for t, col in numeric_cols_meta:
                                is_col_match = col in q_lower or any(cw in q_lower for cw in col.split('_'))
                                if not is_col_match and col in column_synonyms:
                                    is_col_match = any(syn in q_lower for syn in column_synonyms[col])
                                if is_col_match:
                                    best_match_col, best_tbl = col, t
                                    break
                    
                    col_ref = "*"
                    if best_match_col and agg_fn != "COUNT":
                        col_ref = f"{best_tbl}.{best_match_col}" if len(connected_tables) > 1 else best_match_col
                        
                    aggregates_list.append((agg_fn, col_ref))
                    matched_agg = True
                    break
            if matched_agg and not has_and_keyword:
                break

        is_distinct = any(w in q_lower for w in ("distinct", "unique", "different"))

        group_by_col = None
        is_monthly = False
        
        date_cols = []
        for t in connected_tables:
            for col in tables[t]:
                col_type = col_types.get(f"{t}.{col}", "")
                if "date" in col or "time" in col or col_type in ("TIMESTAMP", "DATE", "DATETIME"):
                    date_cols.append((t, col))
                    
        if any(w in q_lower for w in ("monthly", "by month", "month", "over time", "timeline")):
            if date_cols:
                is_monthly = True
                t, col = date_cols[0]
                group_by_col = f"{t}.{col}" if len(connected_tables) > 1 else col

        if not group_by_col:
            dimension_cols = []
            for t in connected_tables:
                for col in tables[t]:
                    if col.endswith("id") or col in ("email", "created_at", "first_name", "last_name", "review_text"):
                        continue
                    if f"{t}.{col}" not in col_types:
                        continue
                    if any(typ in col_types[f"{t}.{col}"] for typ in ("VARCHAR", "TEXT", "CHAR")):
                        dimension_cols.append((t, col))
            
            best_dim = None
            best_score = 0.0
            for t, col in dimension_cols:
                score = fuzzy_score(col, q_lower) + (1.0 if col in q_lower else 0.0)
                if score > best_score:
                    best_score = score
                    best_dim = (t, col)
            if best_dim and best_score > 0.5:
                group_by_col = f"{best_dim[0]}.{best_dim[1]}" if len(connected_tables) > 1 else best_dim[1]
                
        where_filters = []
        having_filters = []
        
        # Default group by to the primary key of the primary table if aggregates or HAVING filters
        # are present, joins exist, and no group_by_col was explicitly matched
        if not group_by_col and (aggregates_list or having_filters) and joins:
            pk = tables[primary_table][0]
            group_by_col = f"{primary_table}.{pk}"
        
        # Extracted numeric filters
        cleaned_q = re.sub(r'\b(top|limit|page)\s+\d+', '', q_lower)
        cleaned_q = re.sub(r'\blast\s+\d+\s+(?:days|months|years|weeks)\b', '', cleaned_q)
        cleaned_q = re.sub(r'\b(?:in|year|since|after|before)\s+\d{4}\b', '', cleaned_q)
        numbers = re.findall(r'\b\d+(?:\.\d+)?\b', cleaned_q)
        for num in numbers:
            pos = cleaned_q.find(num)
            start_idx = max(0, pos - 45)
            context = cleaned_q[start_idx:pos]
            op = '='
            for regex, symbol in operators_map.items():
                if re.search(regex, context):
                    op = symbol
                    break
            best_col = None
            best_tbl = None
            best_score = 0.0
            for tbl in connected_tables:
                for col in tables[tbl]:
                    col_type = col_types.get(f"{tbl}.{col}", "")
                    if not any(typ in col_type for typ in ("INT", "DECIMAL", "FLOAT", "DOUBLE", "NUMERIC", "PRICE", "AMOUNT", "QUANTITY", "RATING")):
                        continue
                    score = fuzzy_score(col, context) + (1.0 if any(cw in context for cw in col.split('_')) else 0.0)
                    if col in column_synonyms:
                        if any(syn in context or syn in q_lower for syn in column_synonyms[col]):
                            score += 1.5
                    if col.endswith("_id") and "id" not in context and "id" not in q_lower:
                        score -= 2.0
                    if score > best_score:
                        best_score = score
                        best_col = col
                        best_tbl = tbl
            if best_col:
                col_ref = f"{best_tbl}.{best_col}" if len(connected_tables) > 1 else best_col
                is_agg = "spent" in cleaned_q or "total" in cleaned_q or "sum" in cleaned_q or "having" in cleaned_q
                clause = f"{col_ref} {op} {num}"
                if is_agg:
                    agg_expr = f"SUM({col_ref})" if "spent" in cleaned_q or "total" in cleaned_q else f"COUNT({col_ref})"
                    having_filters.append(f"{agg_expr} {op} {num}")
                else:
                    where_filters.append(clause)

        # Extracted Text filters
        cities = ["kolkata", "mumbai", "delhi", "bengaluru", "chennai", "new york", "london", "tokyo"]
        countries = ["india", "usa", "uk", "japan"]
        categories = ["electronics", "clothing", "home & kitchen", "home", "kitchen", "books", "sports"]
        statuses = ["completed", "pending", "cancelled", "processing", "shipped"]
        
        for c in cities:
            if c in q_lower:
                tbl = "customers" if "customers" in connected_tables else primary_table
                col_ref = f"{tbl}.city" if len(connected_tables) > 1 else "city"
                where_filters.append(f"{col_ref} = '{c.title()}'")
        for c in countries:
            if c in q_lower:
                tbl = "customers" if "customers" in connected_tables else primary_table
                col_ref = f"{tbl}.country" if len(connected_tables) > 1 else "country"
                val = "USA" if c == "usa" else ("UK" if c == "uk" else c.title())
                where_filters.append(f"{col_ref} = '{val}'")
        for c in categories:
            if c in q_lower:
                tbl = "products" if "products" in connected_tables else primary_table
                col_ref = f"{tbl}.category" if len(connected_tables) > 1 else "category"
                mapped_cat = "Home & Kitchen" if c in ("home", "kitchen", "home & kitchen") else c.title()
                where_filters.append(f"{col_ref} = '{mapped_cat}'")
        for s in statuses:
            if s in q_lower:
                tbl = "orders" if "orders" in connected_tables else primary_table
                col_ref = f"{tbl}.status" if len(connected_tables) > 1 else "status"
                where_filters.append(f"{col_ref} = '{s.capitalize()}'")
        
        quoted = re.findall(r"['\"](.*?)['\"]", question)
        for q_val in quoted:
            pos = question.find(q_val)
            context = question[max(0, pos-20):pos].lower()
            best_col = None
            best_tbl = None
            best_score = 0.0
            for tbl in connected_tables:
                for col in tables[tbl]:
                    if col in ("email", "first_name", "last_name", "product_name", "category", "status", "city"):
                        score = 1.0 if col in context else 0.0
                        if score > best_score:
                            best_score = score
                            best_col = col
                            best_tbl = tbl
            if not best_col:
                best_col = "product_name" if "products" in connected_tables else ("first_name" if "customers" in connected_tables else tables[primary_table][0])
                best_tbl = "products" if "products" in connected_tables else ("customers" if "customers" in connected_tables else primary_table)
            col_ref = f"{best_tbl}.{best_col}" if len(connected_tables) > 1 else best_col
            op = "LIKE" if "name" in best_col or "text" in best_col else "="
            val = f"'%{q_val}%'" if op == "LIKE" else f"'{q_val}'"
            where_filters.append(f"{col_ref} {op} {val}")
            
        date_filters = extract_date_filters(question, tables, col_types, connected_tables, dialect, primary_table)
        for df in date_filters:
            where_filters.append(df["clause"])

        limit_val = 1000
        limit_match = re.search(r"(?:limit|top)\s+(\d+)", q_lower)
        if limit_match:
            limit_val = int(limit_match.group(1))
        elif "top" in q_lower:
            limit_val = 5

        group_by_clause = ""
        order_clause = ""
        sort_col = None
        sort_dir = "DESC" if any(w in q_lower for w in ("top", "highest", "most", "maximum", "expensive", "best")) else "ASC"

        if group_by_col:
            if is_monthly:
                col_ref = f"strftime('%Y-%m', {group_by_col}) AS month" if dialect == "sqlite" else f"DATE_TRUNC('month', {group_by_col}) AS month"
                select_items.append(col_ref)
                group_by_clause = " GROUP BY month"
                sort_col = "month"
                sort_dir = "ASC"
            else:
                select_items.append(group_by_col)
                group_by_clause = f" GROUP BY {group_by_col}"
                
            if aggregates_list:
                for idx, (agg_fn, agg_col) in enumerate(aggregates_list):
                    col_name = agg_col.split('.')[-1] if '.' in agg_col else agg_col
                    alias = f"{agg_fn.lower()}_{col_name if col_name != '*' else 'count'}"
                    select_items.append(f"{agg_fn}({agg_col}) AS {alias}")
                    if idx == 0 and ("top" in q_lower or "highest" in q_lower or "most" in q_lower or "lowest" in q_lower):
                        sort_col = alias
            else:
                select_items.append("COUNT(*) AS count")
                sort_col = "count"
        else:
            if aggregates_list:
                for agg_fn, agg_col in aggregates_list:
                    col_name = agg_col.split('.')[-1] if '.' in agg_col else agg_col
                    alias = f"{agg_fn.lower()}_{col_name if col_name != '*' else 'count'}"
                    select_items.append(f"{agg_fn}({agg_col}) AS {alias}")
            else:
                added_cols = []
                for t in connected_tables:
                    for col in tables[t]:
                        if any(k in col for k in ("name", "title", "subject", "email", "city")):
                            added_cols.append(f"{t}.{col}" if len(connected_tables)>1 else col)
                for t, col in numeric_cols_meta:
                    ref = f"{t}.{col}" if len(connected_tables)>1 else col
                    if ref not in added_cols:
                        added_cols.append(ref)
                pk = tables[primary_table][0]
                pk_ref = f"{primary_table}.{pk}" if len(connected_tables)>1 else pk
                if pk_ref not in added_cols:
                    added_cols.insert(0, pk_ref)
                    
                select_items.extend(added_cols[:5])
                
                if numeric_cols_meta and any(w in q_lower for w in ("top", "highest", "most", "cheapest", "lowest", "expensive", "best")):
                    best_sort_col = None
                    best_sort_tbl = None
                    best_sort_score = 0.0
                    for t, col in numeric_cols_meta:
                        if col.endswith("_id") and col not in q_lower:
                            continue
                        score = fuzzy_score(col, q_lower) + (1.0 if col in q_lower else 0.0)
                        if col in column_synonyms:
                            if any(syn in q_lower for syn in column_synonyms[col]):
                                score += 1.5
                        if score > best_sort_score:
                            best_sort_score = score
                            best_sort_col = col
                            best_sort_tbl = t
                    
                    if best_sort_col:
                        sort_col = f"{best_sort_tbl}.{best_sort_col}" if len(connected_tables)>1 else best_sort_col
                    else:
                        fallback = None
                        for t, col in numeric_cols_meta:
                            if not col.endswith("_id"):
                                fallback = (t, col)
                                break
                        if not fallback and numeric_cols_meta:
                            fallback = numeric_cols_meta[0]
                        if fallback:
                            sort_col = f"{fallback[0]}.{fallback[1]}" if len(connected_tables)>1 else fallback[1]

        if sort_col:
            order_clause = f" ORDER BY {sort_col} {sort_dir}"

        where_clause = ""
        if where_filters:
            where_clause = " WHERE " + " AND ".join(where_filters)
            
        having_clause = ""
        if having_filters:
            having_clause = " HAVING " + " AND ".join(having_filters)

        sql_cols = ", ".join(select_items)
        distinct_str = "DISTINCT " if is_distinct else ""
        
        sql = f"SELECT {distinct_str}{sql_cols} FROM {primary_table}{''.join(joins)}{where_clause}{group_by_clause}{having_clause}{order_clause} LIMIT {limit_val};"

        # 8. Chart Recommendations
        chart_recommended = False
        chart_type = None
        x_axis = None
        y_axes = []
        reasoning = None
        
        if group_by_col:
            chart_recommended = True
            y_axes = [select_items[-1].split(" AS ")[-1]]
            x_axis = "month" if is_monthly else (group_by_col.split(".")[-1] if "." in group_by_col else group_by_col)
            
            if is_monthly:
                chart_type = "line"
                reasoning = "Line charts are ideal for displaying continuous timeline trends."
            elif any(k in x_axis for k in ("status", "category", "country")):
                chart_type = "pie"
                reasoning = "Pie charts show proportions of categorical distributions."
            else:
                chart_type = "bar"
                reasoning = "Bar charts compare aggregate values across grouped dimensions."
        elif len(numeric_cols_meta) > 0 and len(select_items) > 1:
            chart_recommended = True
            chart_type = "bar"
            x_axis = select_items[0].split(" AS ")[-1]
            y_axes = [select_items[1].split(" AS ")[-1]]
            reasoning = f"Visualizes {y_axes[0]} across {x_axis} list."

        # 9. Explanations
        summary = f"Dynamically calculated local compilation query for table '{primary_table}'."
        if aggregates_list:
            agg_details = [f"{fn.lower()} of {col}" for fn, col in aggregates_list]
            summary = f"This query computes the {', and '.join(agg_details)} from '{primary_table}'."
            if group_by_col:
                dim_display = group_by_col.split('.')[-1] if '.' in group_by_col else group_by_col
                summary += f" grouped by {dim_display}"
            if where_filters or having_filters:
                all_filters = where_filters + having_filters
                summary += f" filtered by {', '.join(all_filters)}"
            summary += "."

        tech_details = f"Generates a safe standard SELECT statement from schema analysis. "
        if joins:
            tech_details += f"Performs table relational joins: {' '.join(joins)}."
            
        step_by_step = [
            f"Parsed schema DDL to discover {len(tables)} active tables and relational keys.",
            f"Matched query keywords semantically to target table '{primary_table}'."
        ]
        if joins:
            step_by_step.append(f"Computed shortest BFS connection path: {' -> '.join(connected_tables)}.")
        if where_filters:
            step_by_step.append(f"Applied dynamic column constraints: {', '.join(where_filters)}.")
        if group_by_clause:
            step_by_step.append(f"Grouped records and calculated aggregate metrics.")
        if having_clause:
            step_by_step.append(f"Applied aggregate filters: {', '.join(having_filters)}.")
        if order_clause:
            step_by_step.append(f"Sorted outputs using '{sort_col}' in {sort_dir} order.")

        return {
            "sql": sql,
            "explanation": {
                "business_summary": summary,
                "technical_details": tech_details,
                "step_by_step": step_by_step
            },
            "chart_recommendation": {
                "recommended": chart_recommended,
                "chart_type": chart_type,
                "x_axis_column": x_axis,
                "y_axis_columns": y_axes,
                "reasoning": reasoning
            }
        }

    def generate_sql_response(
        self,
        question: str,
        schema_ddl: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        connection_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Translates the natural language question to a structured SQL response
        using the offline local SQL semantic compiler.
        """
        logger.info("Using local semantic SQL compiler to generate response.")
        return self._generate_local_sql(question, schema_ddl, chat_history, connection_url)

llm_service = LLMService()
