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
                    Baseline dataset shape = 286,296 x 20\n
                    Model Name = Claude 3 Haiku \n
                    Max response size = 25kB
                    ''')

region = os.environ["AWS_REGION"]
agentID = os.environ["BEDROCK_AGENT_ID"]
agentAlias = os.environ["BEDROCK_AGENT_ALIAS"][-10:]

st.sidebar.write("Region: ",region)
st.sidebar.write("Agent ID: ", agentID)
st.sidebar.write("Agent Alias: ", agentAlias)

st.sidebar.subheader(":rocket: Sample questions:")

st.sidebar.markdown('''
                    Show me all KPIs I can query. \n
                    Provide the first 5 rows of all the KPIs I can query. \n
                    Give me two tables. the first table with total cells by governorate. the second table with total cells by vendor. \n
                    Get me a table with the city by city breakdown of the total number of cells and total 4g packet data traffic and the total 4g volte traffic. \n
                    Show me how many cells in the city of Makkah_City have 4g utilization higher than 80%. \n
                    Show me the aggregated total 4g volte traffic and total downlink data traffic for Makkah_City \n
                    Provide a table with the city by city breakdown of total 4g volte traffic. \n
                    Get me a city by city breakdown of average 4g volte traffic. \n
                    Tell me how many cells are of vendor Ericsson ? \n
                    How many cells in the city of Makkah_City have 4g utilization higher than 80% ? \n
                    Show me how many cells have 4g user throughput larger than 150 ? \n
                    What is the total 4g volte traffic across all cells ? \n
                    Provide the top 10 cities in descending order in terms of total number of cells with availability less than 80% \n
                    Show me aggregated data traffic and voice traffic across the vendors Ericsson, Huawei and Nokia. \n
                    Provide a table with the top 10 cells by highest 4g volte traffic ? \n
                    What is the standard deviation of 4g volte traffic across all cells ?
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

# Handling user input and responses
if submit_button and prompt:
    event = {
        "sessionId": "MYSESSION",
        "question": prompt
    }
    
    try: 
        the_response = agenthelper.agent_handler(event, None)
    except:
        the_response = "Apologies, but an error occurred. Please rerun the application"

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