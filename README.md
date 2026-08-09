# PodTok - The AI Educational Video Maker
I created this pipeline to facilitate the creation of fun educational videos.

Turns a topic (optionally grounded in your own uploaded PDFs) into a short and
narrated explainer video; an AI-scripted dialogue between two personas,
rendered with TTS voiceover, reels-style subtitles, and a background video,
ready for Download.

-Link to the app: https://automated-tech-reels-generator.streamlit.app/

-Scroll to the bottom to see how to run locally.

<br>

[![Watch the Demo](demo/Demo_thumbnail.png)](demo/PodTok_product_demo.mp4)

<br>

## How it works

1. **Input & Configuration** — pick an LLM provider (OpenAI, Groq, or local
   Ollama), optionally upload supporting PDFs which get OCR'd, chunked, and
   embedded into a local vector store for grounded context.
2. **Scripting** — the LLM generates a structured dialogue between a
   "Skeptic" and an "Expert" persona, editable in-app before rendering.
3. **Rendering** — text-to-speech per line, karaoke-timed subtitles via
   Whisper transcription, and `ffmpeg` composites everything onto your
   uploaded background video.

### Backend

Small background videos render **synchronously, in-app** for instant results.
Larger uploads are automatically routed through an async pipeline so a single
Streamlit Cloud container never runs out of memory on a big `ffmpeg` job:


Streamlit (UI) ├─ small file → renders locally, in-process 

└─ large file → uploads to Cloudflare R2 → queues a job in Supabase (Postgres) → triggers a GitHub Actions worker instantly via the API → worker downloads from R2, renders, uploads the result back → Streamlit polls and shows the finished video
 

| Problems | Service used | Why |
|---|---|---|
| Job queue / status | Supabase (Postgres) | Lightweight, generous free tier for metadata |
| File storage | Cloudflare R2 | 10GB free, zero egress fees |
| Render compute | GitHub Actions | Free on public repos, triggered instantly via API |


### Tech stack

Streamlit · OpenAI / Groq / Ollama · ChromaDB · PyMuPDF + pdfplumber +
Tesseract OCR · edge-tts · stable-ts (Whisper) · ffmpeg · Supabase · Cloudflare
R2 (boto3) · GitHub Actions




## How to Run Locally
> You dont need the R2/Supabase/GitHub when you run locally, your PC is used as server.

### Prerequisites
- Python 3.11
- `ffmpeg` installed locally (`brew install ffmpeg` / `apt install ffmpeg`)
- Tesseract OCR installed locally if you want PDF ingestion (see
  [Tesseract install docs](https://github.com/tesseract-ocr/tesseract))
-Ollama (if you intend to use this llm)

### Setup

```bash
git clone https://github.com/junior-ta/AI-educational-video-generator.git
cd AI-educational-video-generator
python -m venv venv
source venv/bin/activate  # venv\Scripts\activate on Windows
pip install -r requirements.txt
```



Run it:

```bash
streamlit run app.py
```



