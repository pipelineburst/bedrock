import InvokeAgent as agenthelper
import streamlit as st
import json
import pandas as pd
from PIL import Image

# Streamlit browser tab page configuration
st.set_page_config(page_title="SaaS Agent", page_icon=":robot_face:", layout="wide")

# Title
st.title("Bedrock Agent")
st.header("The agent has access to the baseline test data set")

prompt = st.text_input("Please enter your query?", max_chars=500)

# Display a primary button for submission
submit_button = st.button("Submit", type="primary")

# Display a button to end the session
end_session_button = st.button("End Session")

# Sidebar for general information
description = """
:gray[Explore the chatbot that is backed by Amazon Bedrock Agents, Claude Haiku and a sample dataset.]
"""
with st.sidebar:
    img = Image.open("src/images/mycom-logo-2.png")
    st.image(img)

st.sidebar.title("Agentic GenAI")

st.sidebar.subheader(":rocket: Suggested sample questions:")

st.sidebar.markdown('''
                    Provide a table with the city by city breakdown of the total number of cells and total 4g packet data traffic and  the total 4g volte traffic. \n
                    How many cells in the city of Makkah_City have 4g utilization higher than 80% ? \n
                    What is the aggregated total 4g volte traffic and total downlink data traffic for Makkah_City \n
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
st.sidebar.subheader(":sparkles: Notice and FYI")
st.sidebar.markdown('''
                    Max response size = 25kB \n
                    Baseline dataset shape = 20 x 286,296 \n
                    LLM = Claude Haiku
                    ''')

# Session State Management to build up the conversation history
if 'history' not in st.session_state:
    st.session_state['history'] = []

st.sidebar.subheader(":100: Trace Data")

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
    response = agenthelper.lambda_handler(event, None)
    
    try:
        # Parse the JSON string
        if response and 'body' in response and response['body']:
            response_data = json.loads(response['body'])
            print("TRACE & RESPONSE DATA ->  ", response_data)
        else:
            print("Invalid or empty response received")
    except json.JSONDecodeError as e:
        print("JSON decoding error:", e)
        response_data = None 
    
    try:
        # Extract the response and trace data
        all_data = format_response(response_data['response'])
        the_response = response_data['trace_data']
    except:
        all_data = "..." 
        the_response = "Apologies, but an error occurred. Please rerun the application" 

    # Use trace_data and formatted_response as needed
    st.sidebar.text_area("", value=all_data, height=300)
    st.session_state['history'].append({"question": prompt, "answer": the_response})
    st.session_state['trace_data'] = the_response
    
if end_session_button:
    st.session_state['history'].append({"question": "Session Ended", "answer": "Thank you for using the Agent!"})
    event = {
        "sessionId": "MYSESSION",
        "question": "placeholder to end session",
        "endSession": True
    }
    agenthelper.lambda_handler(event, None)
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