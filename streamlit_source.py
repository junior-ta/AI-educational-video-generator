import streamlit as st 
import ingest

st.title("🎥 AI Instagram reel/tiktok generator")

tab1, tab2, tab3= st.tabs(["Input & Configuration", "Scripting", "Rendering"])

#######################################
#  TAB 1: Input & Configuration
######################################

with tab1:
    st.subheader("1. Configuration🛠️")

    #Model selection
    provider = st.selectbox("AI Provider", ["Groq (Free Llama 3)", "Ollama (Local)", "OpenAI"])

    api_key = None
    ollama_url = "http://localhost:11434"

    if provider == "OpenAI":
        api_key = st.text_input("Provide your OpenAI API Key:", type="password")
        if not api_key:
            st.warning("API Key required for OpenAI.")
    elif provider == "Groq (Free Llama 3)":
        api_key = st.text_input("Groq API Key", type="password", help="Get free key at console.groq.com")
    else:
        ollama_url = st.text_input("Ollama URL", value="http://localhost:11434")
        st.info("Note: 'Localhost' only works if running Streamlit locally, not on Cloud.")

    

    #Spacing
    for i in range(2):
        st.markdown("")


    st.subheader("2. Imports")
    #Spacing
    st.markdown("")
    #ingesting the files
    uploaded_files= st.file_uploader("Attach supporting pdf files🔽", type="pdf", accept_multiple_files=True)

    if st.button("Process Documents"):
        if uploaded_files:
            with st.spinner("Parsing and Ingesting..."):
                # Call ingest.py
                logs = ingest.process_uploaded_files(uploaded_files)
                
                # Show results
                for log in logs:
                    st.write(log)
                st.success("Done!")
        else:
            st.warning("No file was uploaded so the LLM will do its thing!")

    st.markdown("")
    topic= st.chat_input(placeholder="Enter the topic of the video (be as specific as you can ☺︎)")

