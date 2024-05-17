FROM docker.io/library/python:3.12-slim@sha256:afc139a0a640942491ec481ad8dda10f2c5b753f5c969393b12480155fe15a63

WORKDIR /usr/

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt \
    && apt-get update && apt-get -y install \
       vim \
       curl 

# RUN mkdir /usr/src/app/.streamlit
# COPY config.toml /usr/src/app/.streamlit/config.toml 
# ENV STREAMLIT_SERVER_RUN_ON_SAVE=true
# ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
# ENV STREAMLIT_THEME_BASE="dark"
# ENV STREAMLIT_THEME_TEXT_COLOR="#00617F"
# ENV STREAMLIT_THEME_FONT="sans serif"
# ENV STREAMLIT_THEME_BACKGROUND_COLOR="#C1C6C8"
# ENV STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR="#00617F"
# ENV STREAMLIT_THEME_PRIMARY_COLOR="#C1C6C8"

COPY src/ src/

EXPOSE 80

ENTRYPOINT [ "streamlit", "run", "src/app.py", \
             "--server.port", "80", \
             "--server.enableCORS", "true", \
             "--browser.serverAddress", "0.0.0.0", \
             "--browser.serverPort", "443"]