import streamlit as st
import helpers.ingest as ingest, helpers.query_context as query_context, helpers.scripting as scripting, helpers.audio as audio, helpers.subtitles as subtitles, helpers.renderer as renderer
import os
import json
import shutil
import edge_tts
import asyncio
from helpers.supabase_jobs import get_client, create_full_job, create_rerender_job, get_job, update_job
from helpers.r2_helper import upload_file, download_to_file, get_presigned_url, new_object_key
from helpers.github_trigger import trigger_worker_run

# --- Configuration ---
TEMP_DIR = "temp_processing"
os.makedirs(TEMP_DIR, exist_ok=True)

st.title("PodTok")
st.title("🎥 AI Educational Video Maker")

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
    uploaded_files= st.file_uploader("Upload your lesson PDF (Otherwise the content will be generated completely by the LLM)🔽", type="pdf", accept_multiple_files=True)
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

LOCAL_PROCESSING_LIMIT_MB = 10  
supabase_client = get_client()

with tab3:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. Settings 🛠️")
        bg_video = st.file_uploader("Upload Background Video (gameplay, scenery)", type=["mp4", "mov"])
        resolution = st.selectbox("Resolution of the Clip Uploaded", ["1920x1080", "1280x720"])

    with col2:
        actual_voiceS = "en-US-GuyNeural"
        actual_voiceE = "en-US-AriaNeural"

        if 'sample_audioS' not in st.session_state:
            st.session_state.sample_audioS = asyncio.run(
                audio.tts_to_bytes("I am an IBM Z ambassador and I love mainframes!", actual_voiceS, rate="+17%", pitch="+3Hz"))

        if 'sample_audioE' not in st.session_state:
            st.session_state.sample_audioE = asyncio.run(
                audio.tts_to_bytes("I am an IBM Z ambassador and I love mainframes!", actual_voiceE, rate="+10%", pitch="+0Hz"))

        voiceS = st.selectbox("Choose Skeptic's voice", ["en-US-GuyNeural", "en-US-AriaNeural", "en-US-ChristopherNeural", "en-US-EricNeural"])
        if actual_voiceS != voiceS:
            actual_voiceS = voiceS
            st.session_state.sample_audioS = asyncio.run(
                audio.tts_to_bytes("I am an IBM Z ambassador and I love mainframes!", actual_voiceS, rate="+17%", pitch="+3Hz")
            )
        else:
            st.session_state.sample_audioS = asyncio.run(
                audio.tts_to_bytes("I am an IBM Z ambassador and I love mainframes!", actual_voiceS, rate="+17%", pitch="+3Hz"))
        st.audio(st.session_state.sample_audioS, format="audio/mp3")

        voiceE = st.selectbox("AI Expert's voice", ["en-US-AriaNeural", "en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-EricNeural"])
        if actual_voiceE != voiceE:
            actual_voiceE = voiceE
            st.session_state.sample_audioE = asyncio.run(
                audio.tts_to_bytes("I am an IBM Z ambassador and I love mainframes!", actual_voiceE, rate="+10%", pitch="+0Hz")
            )
        else:
            st.session_state.sample_audioE = asyncio.run(
                audio.tts_to_bytes("I am an IBM Z ambassador and I love mainframes!", actual_voiceE, rate="+10%", pitch="+0Hz"))
        st.audio(st.session_state.sample_audioE, format="audio/mp3")

    ##.......parameters state backing....
    for key, default in [
        ("last_generation_params", {}),
        ("final_video_path", None),
        ("subtitle_lines", None),
        ("subtitles_edited", False),
        ("show_subtitle_editor", False),
        ("processing_mode", None),      # "local" or "remote"
        ("job_id", None),
        ("current_job", None),
        ("captions_local_path", None),
        ("job_still_running", False),   # controls whether the auto-poll fragment keeps refreshing
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # To check against history (avoids re-rendering on an unchanged click)
    current_params = {
        "bg_name": bg_video.name if bg_video else None,
        "script_content": str(st.session_state.script_json) if st.session_state.script_json else None,
        "voiceS": voiceS,
        "voiceE": voiceE,
        "resolution": resolution,
        "subtitles": st.session_state.subtitles_edited,
    }

    st.subheader("2. 🎬Output")
    if st.button("Generate Video"):
        if not st.session_state.script_json or st.session_state.script_json is None:
            st.error("Please generate a script in Tab 1 first.")
        elif not bg_video:
            st.error("Please upload a background video and choose a resolution.")
        elif st.session_state.final_video_path and st.session_state.last_generation_params == current_params:
            st.info("no change made!")
        else:
            size_mb = bg_video.size / (1024 * 1024)

            if size_mb <= LOCAL_PROCESSING_LIMIT_MB:
                # --- LOCAL PATH: your original synchronous pipeline, unchanged ---
                st.session_state.processing_mode = "local"
                status = st.empty()
                progress = st.progress(0)

                try:
                    # 1. Save Background Video to disk temporarily
                    bg_path = os.path.join(TEMP_DIR, "background.mp4")
                    with open(bg_path, "wb") as f:
                        f.write(bg_video.getbuffer())

                    # 2. Audio Generation
                    status.write("Generating Audio ...")
                    audio.create_podcast_audio(st.session_state.script_json, voiceS, voiceE)
                    progress.progress(30)

                    # 3. Subtitles
                    if not st.session_state.subtitles_edited:
                        status.write("Generating Subtitles ...")
                        subtitles.generate_subtitles(resolution, "Script_audio.mp3")
                    else:
                        status.write("Using edited subtitles ...")
                    st.session_state.subtitle_lines = subtitles.extract_dialogue_text("Script_captions.ass")
                    st.session_state.captions_local_path = "Script_captions.ass"
                    progress.progress(60)

                    # 4. Rendering
                    status.write("Rendering Video ...")
                    output_video = "final_output.mp4"
                    renderer.render_video(resolution, bg_path, "Script_audio.mp3", "Script_captions.ass", output_file=output_video)
                    progress.progress(100)
                    status.success("Rendering Complete!")

                    st.session_state.last_generation_params = current_params
                    st.session_state.final_video_path = output_video

                except Exception as e:
                    st.error(f"Processing Error: {e}")

            else:
                # --- REMOTE PATH: R2 upload + Supabase job + instant GitHub Actions trigger ---
                st.session_state.processing_mode = "remote"
                try:
                    bg_local = os.path.join(TEMP_DIR, "background.mp4")
                    with open(bg_local, "wb") as f:
                        f.write(bg_video.getbuffer())

                    bg_key = new_object_key("uploads", bg_video.name)
                    upload_file("uploads", bg_local, bg_key)

                    job_id = create_full_job(
                        supabase_client, st.session_state.script_json, voiceS, voiceE, resolution, bg_key
                    )
                    st.session_state.job_id = job_id
                    st.session_state.current_job = None
                    st.session_state.last_generation_params = current_params
                    st.session_state.job_still_running = True  # (re)start the auto-poll fragment

                    if trigger_worker_run():
                        st.info(f"Rendering remotely. Follow Status updates [estimated processing time: 2 mins].")
                    else:
                        st.warning("Job queued, but the instant trigger failed — it'll run within 30 min via the fallback schedule.")
                except Exception as e:
                    st.error(f"Upload/Submit Error: {e}")

    # --- Remote polling: auto-refreshes every 20s while a job is running, no button needed ---
    @st.fragment(run_every=20 if st.session_state.job_still_running else None)
    def poll_job_status():
        if st.session_state.processing_mode != "remote" or not st.session_state.job_id:
            return

        st.session_state.current_job = get_job(supabase_client, st.session_state.job_id)
        job = st.session_state.current_job
        if not job:
            return

        if job["status"] in ("pending", "processing"):
            st.info("Still working on it...")

        #Job terminated here

        was_running = st.session_state.job_still_running
        st.session_state.job_still_running = False

        if job["status"] == "error":
            st.session_state.job_still_running = False
            st.error(f"Failed: {job['error_message']}")

        elif job["status"] == "done":
            st.session_state.job_still_running = False
            video_url = get_presigned_url("outputs", job["output_video_key"])
            st.divider()
            st.subheader("Final Video Preview")
            st.video(video_url)
            st.markdown(f"[Download video]({video_url})")

            if job.get("captions_key") and st.session_state.subtitle_lines is None:
                captions_local = os.path.join(TEMP_DIR, "Script_captions.ass")
                download_to_file("assets", job["captions_key"], captions_local)
                st.session_state.subtitle_lines = subtitles.extract_dialogue_text(captions_local)
                st.session_state.captions_local_path = captions_local

        if was_running:
            st.rerun(scope="app")

    poll_job_status()

    # --- Local video display ---
    if st.session_state.processing_mode == "local" and st.session_state.final_video_path and os.path.exists(st.session_state.final_video_path):
        st.divider()
        st.subheader("Final Video Preview")
        st.video(st.session_state.final_video_path)

        with open(st.session_state.final_video_path, "rb") as file:
            st.download_button(
                label="Download Video",
                data=file,
                file_name="video_generated.mp4",
                mime="video/mp4"
            )

    # --- Subtitle editing (same UI either way; save action differs by mode) ---
    st.divider()

    if st.session_state.subtitle_lines:
        if st.button("✏️ Edit Subtitles"):
            st.session_state.show_subtitle_editor = True
    else:
        st.info("Generate a video first to enable subtitle editing.")

    if st.session_state.show_subtitle_editor:
        edited_text = st.text_area(
            "Edit subtitles (one line per caption)",
            value="\n".join(st.session_state.subtitle_lines),
            height=300
        )

        if st.button("💾 Save Subtitle Changes"):
            updated_lines = edited_text.split("\n")
            subtitles.rewrite_ass_text(st.session_state.captions_local_path, updated_lines)

            st.session_state.subtitle_lines = updated_lines
            st.session_state.subtitles_edited = True
            st.session_state.show_subtitle_editor = False

            if st.session_state.processing_mode == "local":
                st.success("Subtitles saved! Changes will be applied next time you click Generate Video.")
            else:
                # Remote: upload edited captions to R2, submit a lightweight 'rerender' job
                try:
                    edited_key = new_object_key("captions", "Script_captions_edited.ass")
                    upload_file("assets", st.session_state.captions_local_path, edited_key)

                    rerender_job_id = create_rerender_job(supabase_client, st.session_state.current_job, edited_key)
                    st.session_state.job_id = rerender_job_id
                    st.session_state.current_job = None
                    st.session_state.job_still_running = True  # (re)start the auto-poll fragment
                    trigger_worker_run()

                    st.success("Edited subtitles submitted for re-render. Status updates automatically above.")
                except Exception as e:
                    st.error(f"Re-render submit error: {e}")
