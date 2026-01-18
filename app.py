import streamlit as st
import ingest, query_context, scripting, audio, subtitles, renderer
import os
import json
import shutil
import edge_tts
import asyncio

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
                    if st.session_state.script_json==None:
                        st.write("No script was generated (check the console...)")
                    else:                    
                        st.success("✅ Script Generated! Please click on the 'Scripting' tab above to continue.")
                        
                except Exception as e:
                    st.error(f"Error: {e}")
                    
                    


#######################################
#  TAB 2: Scripting
######################################

with tab2:
    st.subheader("Preview Script")
    if st.session_state.script_json==None:
        st.write("No script was generated")
    else:
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
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. Settings 🛠️")
        bg_video = st.file_uploader("Upload Background Video (gameplay, scenery)", type=["mp4", "mov"])
        resolution= st.selectbox("Resolution of the Clip Uploaded", ["1920x1080", "1280x720"])
        

    with col2:
        actual_voiceS="en-US-GuyNeural" 
        actual_voiceE="en-US-AriaNeural"       
        
        if 'sample_audioS' not in st.session_state:
            st.session_state.sample_audioS = asyncio.run(
                audio.tts_to_bytes("I am an IBM Z ambassador and I love mainframes!", actual_voiceS, rate="+17%", pitch="+3Hz"))
        
        if 'sample_audioE' not in st.session_state:
            st.session_state.sample_audioE = asyncio.run(
                audio.tts_to_bytes("I am an IBM Z ambassador and I love mainframes!", actual_voiceE, rate="+10%", pitch="+0Hz"))
        

        voiceS= st.selectbox("Choose Skeptic's voice", ["en-US-GuyNeural", "en-US-AriaNeural", "en-US-ChristopherNeural", "en-US-EricNeural"])
        if  actual_voiceS != voiceS:
            actual_voiceS= voiceS
            st.session_state.sample_audioS = asyncio.run(
                audio.tts_to_bytes("I am an IBM Z ambassador and I love mainframes!", actual_voiceS, rate="+17%", pitch="+3Hz")
            )
        else:
            st.session_state.sample_audioS = asyncio.run(
                audio.tts_to_bytes("I am an IBM Z ambassador and I love mainframes!", actual_voiceS, rate="+17%", pitch="+3Hz"))            
        st.audio(st.session_state.sample_audioS, format="audio/mp3")

        voiceE= st.selectbox("AI Expert's voice", ["en-US-AriaNeural", "en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-EricNeural"])
        if  actual_voiceE != voiceE:
            actual_voiceE= voiceE
            st.session_state.sample_audioE = asyncio.run(
                audio.tts_to_bytes("I am an IBM Z ambassador and I love mainframes!", actual_voiceE, rate="+10%", pitch="+0Hz")
            )
        else:
            st.session_state.sample_audioE = asyncio.run(
                audio.tts_to_bytes("I am an IBM Z ambassador and I love mainframes!", actual_voiceE, rate="+10%", pitch="+0Hz"))            
        st.audio(st.session_state.sample_audioE, format="audio/mp3")

    ##.......parameters state backing....
    if "last_generation_params" not in st.session_state:
        st.session_state.last_generation_params = {}

    if "final_video_path" not in st.session_state:
        st.session_state.final_video_path = None

    # To check against history
    current_params = {
        "bg_name": bg_video.name if bg_video else None,
        "script_content": str(st.session_state.script_json) if st.session_state.script_json else None,
        "voiceS": voiceS,
        "voiceE": voiceE,
        "resolution": resolution
    }


    st.subheader("2. 🎬Output")
    if st.button("Generate Video"):
        if not st.session_state.script_json or st.session_state.script_json==None:
            st.error("Please generate a script in Tab 1 first.")
        elif not bg_video:
            st.error("Please upload a background video and choose a resoltion.")
        else:
            if st.session_state.final_video_path and st.session_state.last_generation_params == current_params:
                st.info("no change made!")
            else:
                status = st.empty()
                progress = st.progress(0)
                
                try:
                    # 1. Save Background Video to disk temporarily
                    bg_path = os.path.join(TEMP_DIR, "background.mp4")
                    with open(bg_path, "wb") as f:
                        f.write(bg_video.getbuffer())
                    
                    # 2. Audio Generation
                    status.write("Generating Audio ...")
                    # We need to make create_podcast_audio synchronous or run it properly
                    # Assuming audio.py saves to 'final_audio.mp3'
                    audio.create_podcast_audio(st.session_state.script_json, voiceS, voiceE)
                    progress.progress(30)
                    
                    # 3. Subtitles
                    status.write("Generating Subtitles ...")
                    subtitles.generate_subtitles(resolution, "Script_audio.mp3")
                    progress.progress(60)
                    
                    # 4. Rendering
                    status.write("Rendering Video ...")
                    output_video = "final_output.mp4"
                    renderer.render_video(resolution, bg_path, "Script_audio.mp3", "Script_captions.ass", output_file=output_video)
                    progress.progress(100)
                    
                    status.success("Rendering Complete!")

                    # 4.2 Save parameters
                    st.session_state.last_generation_params= current_params
                    st.session_state.final_video_path= output_video
                
                except Exception as e:
                    st.error(f"Processing Error: {e}")

    # 5. Display
    if st.session_state.final_video_path and os.path.exists(st.session_state.final_video_path):
            st.divider()
            st.subheader("Final Video Preview")
            st.video(st.session_state.final_video_path)
            
            # 6. Download Button
            with open(st.session_state.final_video_path, "rb") as file:
                st.download_button(
                    label="Download Video",
                    data=file,
                    file_name="video_generated.mp4",
                    mime="video/mp4"
                )  