import streamlit as st 
import ingest

st.title("AI Instagram reel/tiktok generator")

st.subheader("1. Configuration🛠️")

#Spacing
for i in range(2):
    st.markdown("")
#ingesting the files
uploaded_files= st.file_uploader("import supporting pdf files🔽", type="pdf", accept_multiple_files=True)

if st.button("Process Documents"):
    if uploaded_files:
        with st.spinner("Parsing and Ingesting..."):
            # Call the new function in ingest.py
            logs = ingest.process_uploaded_files(uploaded_files)
            
            # Show results
            for log in logs:
                st.write(log)
            st.success("Done!")
    else:
        st.warning("No file was uploaded so the LLM will do its thing!")

