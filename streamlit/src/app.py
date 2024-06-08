import InvokeAgent as agenthelper
import streamlit as st
import json
import pandas as pd
from PIL import Image
import os

# Streamlit browser tab page configuration
st.set_page_config(page_title="SaaS Agent", page_icon=":robot_face:", layout="wide")

# Title
st.title("Bedrock Agent")
st.header("The agent has access to the baseline test data set")

prompt = st.text_input(label="Please enter your question", max_chars=500)

# Display a primary button for submission
submit_button = st.button(label="Submit", type="primary")

# Display a button to end the session
end_session_button = st.button(label="End Session", type="secondary")

# Sidebar for general information
description = """
:gray[Explore the chatbot that is backed by Amazon Bedrock Agents, Claude Haiku and a sample dataset.]
"""
with st.sidebar:
    img = Image.open("src/images/mycom-logo-2.png")
    st.image(img)

st.sidebar.title("Agentic GenAI")

st.sidebar.subheader(":sparkles: Notice and FYI")

st.sidebar.markdown('''
                    Baseline dataset = 45M records as 280k x 20 x 8\n
                    Data granularity = Day level\n
                    Data periods = 10-17 Feb 2024\n
                    Model Name = Claude 3 Haiku \n
                    Max response size = 25kB
                    ''')

region = os.environ["AWS_REGION"]
agentID = os.environ["BEDROCK_AGENT_ID"]
agentAlias = os.environ["BEDROCK_AGENT_ALIAS"][-10:]

st.sidebar.write("Region: ",region)
st.sidebar.write("Agent ID: ", agentID)
st.sidebar.write("Agent Alias: ", agentAlias)

st.sidebar.subheader(":rocket: One-Shot Sample Questions:")

st.sidebar.markdown('''
                    Show me all KPIs I can query. \n
                    Provide the first 5 rows of all the KPIs I can query. \n
                    Provide a KPI overview by city. \n
                    What is the total 4g volte traffic by date for 10 Feb and 11 Feb. \n
                    Provide the data traffic by vendor. Add separate columns for each date. \n
                    Give me a table with the cell count by city. Add separate columns for each vendor. \n
                    Get me a table with the city by city breakdown of the total number of cells and total 4g packet data traffic and the total 4g volte traffic. \n
                    Use vendor, technology and city and provide the number of cells for each ranked from highest to lowest in a table. \n 
                    Show me how many cells in the city of Makkah_City have 4g utilization higher than 80%. \n
                    Provide a table with the city by city breakdown of total 4g volte traffic. \n
                    Show me the aggregated total 4g volte traffic and total downlink data traffic for Makkah_City. \n
                    What is the total packet data traffic by city in GB and TB. \n
                    Show me the total volte traffic by city in GB and Erlans. \n
                    Show me the total volte traffic by city for Feb 11 in GB and Erlangs. \n
                    Provide the top 10 list of cells in the city of Riyadh_City ranked by highest 4G drop packet rate. Exclude cells that have 4g data traffic of less than 10 GB. Add a column with the 4g data traffic. \n
                    Provide a table with total number of cells by city and 3 other columns with the split per vendor Ericsson, Huawei and Nokia. \n
                    How many cells in the city of Makkah_City have 4g utilization higher than 80% ? \n
                    Show me how many cells have 4g user throughput larger than 150 ? \n
                    What is the total 4g volte traffic across all cells ? \n
                    Provide the top 10 cities in descending order in terms of total number of cells with availability less than 80%. \n
                    Show me aggregated data traffic and voice traffic across the vendors Ericsson, Huawei and Nokia. \n
                    Provide a table with the top 10 cells by highest 4g volte traffic. \n
                    What is the standard deviation of 4g volte traffic across all cells ? \n 
                    Provide a city breakdown of the average voice traffic and data traffic. Also add separate columns for the median and 25th percentile, 75th percentile. \n
                    Identify the cell in Riyadh city that has the highest 4G packet drop rate and a packet traffic greater that 10 GB \n
                        ''')

st.sidebar.subheader(":rocket: Few-Shot Sample Questions:")

st.sidebar.markdown('''
                    Provide the cell with the highest data traffic which is not rural, provide also voice traffic and city for that cell, all together in a table. \n
                    Provide the data traffic and user throughput KPIs for that cell for the past 8 days in table format. Also add the vendor as a column.\n
                    Provide the VoLTE Traffic by city and return the top 10 cities in descending order. Exclude the Rural city. \n
                    Provide the average 4g volte traffic for those cities. Also provide the median as a separate column. \n
                    Drill into the Riyadh_City and provide the top 10 cells by data traffic. \n
                    Add the volte traffic KPIs to the result table \n
                    ''')

# Session State Management to build up the conversation history
if 'history' not in st.session_state:
    st.session_state['history'] = []

# Function to parse and format response
def format_response(response_body):
    try:
        # Try to load the response as JSON
        data = json.loads(response_body)
        # If it's a list, convert it to a DataFrame for better visualization
        if isinstance(data, list):
            return pd.DataFrame(data)
        else:
            return response_body
    except json.JSONDecodeError:
        # If response is not JSON, return as is
        return response_body

# Handling user input and responses. The session id should be unique for each conversation id and should not be hard coded as shown here.
if submit_button and prompt:
    event = {
        "sessionId": "MYSESSION",
        "question": prompt
    }
    
    try: 
        the_response = agenthelper.agent_handler(event, None)
    except:
        the_response = "Apologies, but an error occurred. Please adjust the question and rerun the query."

    # Add the conversation to the history
    st.session_state['history'].append({"question": prompt, "answer": the_response})
    
if end_session_button:
    st.session_state['history'].append({"question": "Session Ended", "answer": "Thank you for using the Agent!"})
    event = {
        "sessionId": "MYSESSION",
        "question": "placeholder to end session",
        "endSession": True
    }
    agenthelper.agent_handler(event, None)
    st.session_state['history'].clear()

# Display conversation history
st.write("## Conversation History")
st.write("### Latest entry on top")

for chat in reversed(st.session_state['history']):
    
    message = st.chat_message("user")
    message.write(chat["question"])
    if isinstance(chat["answer"], pd.DataFrame):
        st.dataframe(chat["answer"])
    else:
        answer = st.chat_message("assistant")
        answer.write(chat["answer"])