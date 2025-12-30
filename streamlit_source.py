import streamlit as st
import ingest, query_context, scripting, audio, subtitles, renderer
import os
import json
import shutil

# --- Configuration ---
TEMP_DIR = "temp_processing"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

st.title("🎥 AI Instagram reel/tiktok generator")

tab1, tab2, tab3= st.tabs(["Input & Configuration", "Scripting", "Rendering"])

#######################################
#  TAB 1: Input & Configuration
######################################

with tab1:
    st.subheader("1. Configuration🛠️")

    #Model selection
    provider = st.selectbox("AI Provider", ["Groq", "Ollama", "OpenAI"])

    api_key = None
    ollama_url = "http://localhost:11434"

    if provider == "OpenAI":
        api_key = st.text_input("Provide your OpenAI API Key:", type="password")
        if not api_key:
            st.warning("API Key required for OpenAI.")
    elif provider == "Groq":
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
    upload_process=0

    if st.button("Process Documents"):
        if uploaded_files:
            with st.spinner("Parsing and Ingesting..."):
                # Call ingest.py
                logs = ingest.process_uploaded_files(uploaded_files)
                
                # Show results
                for log in logs:
                    st.write(log)
                upload_process=1
                st.success("Done!")
        else:
            st.warning("No file was uploaded so the LLM will do its thing!")

    st.markdown("")
    topic= st.chat_input(placeholder="Enter the topic of the video (be as specific as you can ☺︎)")

# Script generation
    if "script_json" not in st.session_state:
        st.session_state.script_json = None
    
    if topic:
        if upload_process:
            st.warning("Either the files provided are still being injested or you did not provide any supporting file! The LLM will do its thing")
        else:
            # 1. Retrieve Context
            context, sources = query_context.query_context(topic)
            if not context:
                st.warning("No specific context found in DB. Using general LLM knowledge.")
            
            # 2. Generate Script
            with st.spinner("Consulting the Expert and the Skeptic..."):
                try:
                    script = scripting.generate_script(
                        topic, 
                        context, 
                        provider=provider, 
                        api_key=api_key, 
                        ollama_url=ollama_url
                    )
                    st.session_state.script_json = script
                    st.success("✅ Script Generated! Please click on the 'Scripting' tab above to continue.")
                except Exception as e:
                    st.error(f"Error: {e}")


#######################################
#  TAB 2: Scripting
######################################

with tab2:
    st.subheader("Preview Script")
    st.write("When you are satisfied with the script, proceed to the Rendering tab by clicking on 'Rendering' above")

    #state is preview or edit
    if "mode" not in st.session_state:
        st.session_state.mode = "preview"

    if st.session_state.script_json:
        
        if st.session_state.mode == "preview":
            if st.button("modify script"):
                st.session_state.mode = "edit"
                st.rerun()
        
            for line in st.session_state.script_json:
                speaker = line['speaker']
                text = line['text']
                if speaker == "Skeptic":
                    st.markdown(f"**😒 {speaker}:** {text}")
                else:
                    st.markdown(f"**🤓 {speaker}:** {text}")

        elif st.session_state.mode == "edit":
            
            #help to switch back to preview mode
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Done editing"):
                    st.session_state.mode = "preview"
                    st.rerun()
            with col2:
                if st.button("Cancel"):
                    st.session_state.mode = "preview"
                    st.rerun()

            #DATA EDITOR
            # It takes the JSON list and shows it as an editable table. Captures the return value ('edited_script') to update our state.
            edited_script = st.data_editor(
                st.session_state.script_json,
                num_rows="dynamic",  # User can add/delete rows
                width='stretch',
                column_config={
                    "speaker": st.column_config.SelectboxColumn(
                        "Speaker",
                        width='small',
                        options=["Skeptic", "Expert"], # Restrict choices to prevent typos
                        required=True
                    ),
                    "text": st.column_config.TextColumn(
                        "Dialogue",
                        width="large",
                        required=True
                    )
                },
                key="editor"
            )

            # Sync changes back to session_state immediately
            if edited_script != st.session_state.script_json:
                st.session_state.script_json = edited_script
                # data_editor updates the state automatically on interaction

            st.divider()
            
            # Visualize the Chat (Read-Only View)
            st.subheader("Final Preview")
            for line in st.session_state.script_json:
                speaker = line.get('speaker', 'Unknown')
                text = line.get('text', '...')
                if speaker == "Skeptic":
                    st.markdown(f"**😒 {speaker}:** {text}")
                else:
                    st.markdown(f"**🤓 {speaker}:** {text}")



#######################################
#  TAB 3: Rendering
######################################

with tab3:
    st.subheader("1. Settings 🛠️")

    st.subheader("2. 🎬Output")