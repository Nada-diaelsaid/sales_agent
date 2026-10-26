#!/usr/bin/env python
from openai import OpenAI
import pandas as pd
import json
import duckdb
from pydantic import BaseModel, Field
from IPython.display import Markdown

from helper import get_openai_api_key, get_phoenix_endpoint

import phoenix as px
import os
from phoenix.otel import register
from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.semconv.trace import SpanAttributes
from opentelemetry.trace import Status, StatusCode
from openinference.instrumentation import TracerProvider

# print(px)
# initialize the OpenAI client
openai_api_key = get_openai_api_key()
client = OpenAI(api_key=openai_api_key)

MODEL = "gpt-4o-mini"
# print(get_phoenix_endpoint())
PROJECT_NAME = "tracing-agent"

# Connect OpenTelemetry to Phoenix to be able to visualize traces in the Phoenix dashboard. 
# The register function will return a TracerProvider that can be used to create spans and add attributes to them.
# We can access the Phoenix dashboard at the endpoint returned by get_phoenix_endpoint() + "v1/traces"
tracer_provider = register(
    project_name=PROJECT_NAME)
session = px.launch_app()

# Tool 1: Database Lookup
# define the path to the transactional data
# The agent will need to access this data to answer questions about sales, price elasticity, and promotions.
TRANSACTION_DATA_FILE_PATH = 'data/Store_Sales_Price_Elasticity_Promotions_Data.parquet'

# 1. First, it creates the SQL table from a local file, if not already done.
# 2. Second, it translates the original prompt into an sql query (using an LLM call).
# 3. Finally, it runs that query against the database.

# prompt template for step 2 of tool 1
SQL_GENERATION_PROMPT = """
Generate an SQL query based on a prompt. Do not reply with anything besides the SQL query.
The prompt is: {prompt}

The available columns are: {columns}
The table name is: {table_name}
"""

# code for step 2 of tool 1
def generate_sql_query(prompt: str, columns: list, table_name: str) -> str:
    """Generate an SQL query based on a prompt"""

    # Format the prompt with the available columns and table name
    # string.format() Inserts specified values into a string placeholder defined by curly brackets {}
    formatted_prompt = SQL_GENERATION_PROMPT.format(prompt=prompt, 
                                                    columns=columns, 
                                                    table_name=table_name)

    # Send this formatted prompt to the LLM to generate the SQL query
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": formatted_prompt}],
    )
    
    return response.choices[0].message.content

# code for tool 1
# This function will be called by the agent to look up sales data based on a prompt.
def lookup_sales_data(prompt: str) -> str:
    """Implementation of sales data lookup from parquet file using SQL"""
    try:

        # define the table name
        table_name = "sales"
        
        # step 1: read the parquet file into a DuckDB table
        df = pd.read_parquet(TRANSACTION_DATA_FILE_PATH)
        duckdb.sql(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM df")

        # step 2: generate the SQL code
        sql_query = generate_sql_query(prompt, df.columns, table_name)
        # clean the response to make sure it only includes the SQL code
        # as an LLM can sometimes include extra text or formatting, we need to clean it up.
        sql_query = sql_query.strip()
        sql_query = sql_query.replace("```sql", "").replace("```", "")
        
        # step 3: execute the SQL query
        result = duckdb.sql(sql_query).df()
        
        return result.to_string()
    except Exception as e:
        return f"Error accessing data: {str(e)}"

example_data = lookup_sales_data(prompt="Show me all sales for store 1320 in the month of January of 2023")
# print(example_data)

"""
      Store_Number  SKU_Coded  Product_Class_Code  Sold_Date  Qty_Sold  Total_Sale_Value  On_Promo
0             1320    6173050               22875 2023-01-09         2          9.980000         0
1             1320    6173050               22875 2023-01-16         1          4.990000         0
2             1320    6173350               22800 2023-01-01         1          8.790000         0
3             1320    6173350               22800 2023-01-03         1          8.790000         0
4             1320    6173350               22800 2023-01-11         1          8.790000         0
"""
############################################################################################

# The second tool can analyze the returned data and display conclusions to users.
# Construct prompt based on analysis type and data subset
DATA_ANALYSIS_PROMPT = """
Analyze the following data: {data}
Your job is to answer the following question: {prompt}
"""

# code for tool 2
def analyze_sales_data(prompt: str, data: str) -> str:
    """Implementation of AI-powered sales data analysis"""
    formatted_prompt = DATA_ANALYSIS_PROMPT.format(data=data, prompt=prompt)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": formatted_prompt}],
    )
    
    analysis = response.choices[0].message.content
    # Important to check if the analysis is empty or not, as the LLM may sometimes return an empty response.
    return analysis if analysis else "No analysis could be generated"

analysis_result = analyze_sales_data(prompt="what trends do you see in this data", data=example_data)
# print(analysis_result)
"""
1. **Sales Volume and Revenue**: 
   - The data shows a variety of products with different quantities sold over the dates provided. The `Qty_Sold` indicates the volume sold for each SKU, while the `Total_Sale_Value` gives insight into the revenue generated.
   - A general pattern can be derived by summing quantity sold and total sales value to identify which products generate the most revenue and volume.

2. **Product Class Codes**:
   - Products have different `Product_Class_Code` which appears to categorize them. By aggregating sales and quantities by this product class, one can identify which categories perform well.
   
3. **Promotions**: 
   - The dataset includes a column for promotional status (`On_Promo`). However, all entries are marked as `0`, suggesting that this dataset does not contain any promotional sales information. This limits the analysis for sales driven by promotions.

4. **Time Trends**:
   - The `Sold_Date` provides an opportunity to assess seasonal trends or patterns over time. By extracting the month or week from thedate, we can observe if certain weeks of January show spikes in sales compared to others.
   - For example, weekends or specific weeks might show higher sales due to holiday promotions or events but, as the data does not extend beyond January, a full month comparison constrains this analysis.

5. **Top Selling Products**:
   - Identifying top-selling products would involve calculating total quantity and sales per SKU. Some products may appear frequently with varying quantities sold across dates. Benchmarking these periodically could uncover consistent best-sellers.

6. **Price Analysis**:
   - Analyzing `Total_Sale_Value` relative to `Qty_Sold` can provide insight into the average price per unit sold. Fluctuations in these values can indicate pricing strategy effectiveness.

### Preliminary Findings:
- **Top Performers**: It seems there is significant variation in the sales quantity among products; specific products likely bring in higher revenue.
- **Repetition in Sales**: Certain SKUs appear repeatedly, possibly indicating that these products are staples, regularly bought items, or seasonal items that lead to consistent sales.
- **Sales Concentration**: The data can reveal whether sales are concentrated on a few products or well-distributed across numerous SKUs, which can inform inventory and stock strategies.
- **Potential for Promotions**: Since the `On_Promo` column is unused, there's an opportunity to analyze the effectiveness of promotions if the data were available.
- **Fluctuations in Prices**: Assessing the variability in `Total_Sale_Value` in connection to quantities sold could provide insight into customer purchasing decisions based on price changes.

### Recommendations for Further Analysis:
- Expand on the current dataset to include promotional periods and assess their impact on sales and revenue.
- Include comparative historical data to evaluate performance trends over time.
- Conduct cluster analysis on product performance to categorize slow versus fast-moving goods.
- Analyze customer demographics or segmentation (if available) to understand different purchasing behaviors further.

By using this analysis, a comprehensive overview of sales trends, product performance, and revenue generation can emerge, aiding in informed decision-making for inventory management, marketing, and sales strategies.
"""
############################################################################################

# The third tool generates python code to create the requested graphs from the returned data of the first tool. It consists of two steps:
# 1. First, it creates the chart configuration: chart type, title, data, lables for x-axis and y-axis (using an LLM call).
# 2. Second, it generates the python code based on the chart configuration of the first step (using an LLM call).
# we divided our goal here into 2 steps to make it easier for the LLM to generate the code, as generating code directly from a prompt can be more challenging.

# prompt template for step 1 of tool 3
CHART_CONFIGURATION_PROMPT = """
Generate a chart configuration based on this data: {data}
The goal is to show: {visualization_goal}
"""
# We will use pydantic along with openAI feature called StructuredOutput to make sure when you make a call to generate the chart configuration, the response is formatted as intended and can be easily parsed into a Python object.
  
# class defining the response format of step 1 of tool 3
class VisualizationConfig(BaseModel): # inherits from BaseModel/pydantic to define a structured output model for the chart configuration
    # a dict with 4 keys: chart_type, x_axis, y_axis, title
    chart_type: str = Field(..., description="Type of chart to generate")
    x_axis: str = Field(..., description="Name of the x-axis column")
    y_axis: str = Field(..., description="Name of the y-axis column")
    title: str = Field(..., description="Title of the chart")

# code for step 1 of tool 3
def extract_chart_config(data: str, visualization_goal: str) -> dict:
    """Generate chart visualization configuration
    
    Args:
        data: String containing the data to visualize
        visualization_goal: Description of what the visualization should show
        
    Returns:
        Dictionary containing line chart configuration
    """
    formatted_prompt = CHART_CONFIGURATION_PROMPT.format(data=data,
                                                         visualization_goal=visualization_goal)

    # The call here is a bit different, as we are using the new StructuredOutput feature of OpenAI to let OpenAI format it in the way we want
    response = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[{"role": "user", "content": formatted_prompt}],
        response_format=VisualizationConfig,
    )
    
    try:
        # Extract axis and title info from response
        content = response.choices[0].message.content
        
        # Return structured chart config
        return {
            "chart_type": content.chart_type,
            "x_axis": content.x_axis,
            "y_axis": content.y_axis,
            "title": content.title,
            "data": data
        }
    except Exception:
        return {
            "chart_type": "line", 
            "x_axis": "date",
            "y_axis": "value",
            "title": visualization_goal,
            "data": data
        }

# prompt template for step 2 of tool 3
CREATE_CHART_PROMPT = """
Write python code to create a chart based on the following configuration.
Only return the code, no other text.
config: {config}
"""

# code for step 2 of tool 3
def create_chart(config: dict) -> str:
    """Create a chart based on the configuration
    Take the dict generated from lasts step."""
    formatted_prompt = CREATE_CHART_PROMPT.format(config=config)
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": formatted_prompt}],
    )
    
    code = response.choices[0].message.content
    code = code.replace("```python", "").replace("```", "")
    # generate python code to create a chart based on the configuration
    code = code.strip()
    
    return code

# code for tool 3
def generate_visualization(data: str, visualization_goal: str) -> str:
    """Generate a visualization based on the data and goal"""
    config = extract_chart_config(data, visualization_goal)
    code = create_chart(config)
    return code

code = generate_visualization(example_data, 
                              "A bar chart of sales by product SKU. Put the product SKU on the x-axis and the sales on the y-axis.")
print(code)
# Run the generated code, should pop up the chart in a new windows.
# Always be careful when running code generated by an LLM, as it may contain errors or malicious code. Always review the code before executing it, or always run it in a safe environment. In this case, we are running it in a Jupyter notebook, which is a safe environment for running code.
exec(code)

# Define tools/functions that can be called by the model
tools = [
    {
        "type": "function",
        "function": {
            "name": "lookup_sales_data",
            "description": "Look up data from Store Sales Price Elasticity Promotions dataset",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The unchanged prompt that the user provided."}
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_sales_data", 
            "description": "Analyze sales data to extract insights",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "string", "description": "The lookup_sales_data tool's output."},
                    "prompt": {"type": "string", "description": "The unchanged prompt that the user provided."}
                },
                "required": ["data", "prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_visualization",
            "description": "Generate Python code to create data visualizations",
            "parameters": {
                "type": "object", 
                "properties": {
                    "data": {"type": "string", "description": "The lookup_sales_data tool's output."},
                    "visualization_goal": {"type": "string", "description": "The goal of the visualization."}
                },
                "required": ["data", "visualization_goal"]
            }
        }
    }
]

# Dictionary mapping function names to their implementations
tool_implementations = {
    "lookup_sales_data": lookup_sales_data,
    "analyze_sales_data": analyze_sales_data, 
    "generate_visualization": generate_visualization
}

# code for executing the tools returned in the model's response
def handle_tool_calls(tool_calls, messages):
    
    for tool_call in tool_calls:   
        function = tool_implementations[tool_call.function.name]
        function_args = json.loads(tool_call.function.arguments)
        result = function(**function_args)
        messages.append({"role": "tool", "content": result, "tool_call_id": tool_call.id})
        
    return messages

SYSTEM_PROMPT = """
You are a helpful assistant that can answer questions about the Store Sales Price Elasticity Promotions dataset.
"""

def run_agent(messages):
    print("Running agent with messages:", messages)

    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
        
    # Check and add system prompt if needed
    if not any(
            isinstance(message, dict) and message.get("role") == "system" for message in messages
        ):
            system_prompt = {"role": "system", "content": SYSTEM_PROMPT}
            messages.append(system_prompt)

    while True:
        print("Making router call to OpenAI")
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
        )
        messages.append(response.choices[0].message)
        tool_calls = response.choices[0].message.tool_calls
        print("Received response with tool calls:", bool(tool_calls))

        # if the model decides to call function(s), call handle_tool_calls
        if tool_calls:
            print("Processing tool calls")
            messages = handle_tool_calls(tool_calls, messages)
        else:
            print("No tool calls, returning final response")
            return response.choices[0].message.content



result = run_agent('Show me the code for graph of sales by store in Nov 2021, and tell me what trends you see.')
