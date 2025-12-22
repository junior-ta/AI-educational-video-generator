import fitz  # PyMuPDF
import pdfplumber
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os

# --- Configuration ---
PDF_PATH = "example.pdf"  # Change this to your target PDF
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "manual_ingest"

def is_inside_bbox(block_bbox, table_bboxes):
    """
    Checks if a text block is contained within any of the detected table bounding boxes.
    Refines parsing by ignoring raw text that is actually part of a table.
    """
    bx0, by0, bx1, by1 = block_bbox
    
    for t_bbox in table_bboxes:
        # pdfplumber format: (x0, top, x1, bottom)
        tx0, ty0, tx1, ty1 = t_bbox
        
        # Check for significant overlap (if the text block is mostly inside the table)
        if (bx0 >= tx0 and bx1 <= tx1 and by0 >= ty0 and by1 <= ty1):
            return True
    return False

def parse_pdf_dual_pass(pdf_path):
    """
    Pass 1: Use pdfplumber to extract tables and their coordinates.
    Pass 2: Use PyMuPDF to extract text blocks, filtering out those inside tables.
    Merge: Combine text and markdown tables based on vertical position (reading order).
    """
    full_text = ""
    
    # Open with both libraries
    with pdfplumber.open(pdf_path) as plumber_pdf, fitz.open(pdf_path) as fitz_pdf:
        
        for page_num, plumber_page in enumerate(plumber_pdf.pages):
            fitz_page = fitz_pdf[page_num]
            
            # --- PASS 1: Table Extraction (pdfplumber) ---
            tables = plumber_page.find_tables()
            table_data = []
            table_bboxes = []

            for table in tables:
                # Get the bounding box of the table
                table_bboxes.append(table.bbox)
                
                # Extract table content and convert to Markdown
                # We use extract_tables to get the data, then pandas or manual formatting
                # Here is a simple manual conversion to Markdown
                raw_table = table.extract()
                markdown_table = ""
                if raw_table:
                    # Create header
                    if raw_table[0]:
                        markdown_table += "| " + " | ".join(map(str, raw_table[0])) + " |\n"
                        markdown_table += "| " + " | ".join(["---"] * len(raw_table[0])) + " |\n"
                    # Create rows
                    for row in raw_table[1:]:
                        # Handle None values in cells
                        clean_row = [str(cell) if cell is not None else "" for cell in row]
                        markdown_table += "| " + " | ".join(clean_row) + " |\n"
                
                # Store (y-coordinate, content) for sorting later
                # We use the top y-coordinate (table.bbox[1]) to place it in the stream
                table_data.append((table.bbox[1], markdown_table))

            # --- PASS 2: Text Extraction (PyMuPDF) ---
            # 'blocks' returns a list of items: (x0, y0, x1, y1, "text", block_no, block_type)
            text_blocks = fitz_page.get_text("blocks")
            text_data = []

            for block in text_blocks:
                # block[4] is the text content
                # block[:4] is the bbox (x0, y0, x1, y1)
                block_bbox = block[:4]
                block_text = block[4]

                # Filter: If this text block is actually inside a table, ignore it
                # (because we already captured it as a Markdown table above)
                if not is_inside_bbox(block_bbox, table_bboxes):
                    # Store (y-coordinate, content)
                    text_data.append((block_bbox[1], block_text))

            # --- MERGE & SORT ---
            # Combine tables and text
            all_content = table_data + text_data
            
            # Sort by vertical position (y0) to maintain reading order
            all_content.sort(key=lambda x: x[0])
            
            # Join into a single string for the page
            page_content = "\n".join([item[1] for item in all_content])
            full_text += f"\n--- Page {page_num + 1} ---\n{page_content}"
            
            print(f"Processed Page {page_num + 1}...")

    return full_text

def chunk_text(text):
    """
    Split text into manageable chunks with overlap to maintain context.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_text(text)
    return chunks

def ingest_to_chroma(chunks):
    """
    Initialize ChromaDB and store vectors.
    """
    # Initialize Client (Persistent storage)
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    
    # Get or Create Collection
    # Note: Chroma uses 'all-MiniLM-L6-v2' as default embedding function if none provided
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    # Prepare data for insertion
    # Chroma requires unique IDs for each document
    ids = [f"id_{i}" for i in range(len(chunks))]
    metadatas = [{"source": "manual_ingest"} for _ in chunks]

    print(f"Upserting {len(chunks)} chunks to ChromaDB...")
    
    # Add to collection
    collection.add(
        documents=chunks,
        metadatas=metadatas,
        ids=ids
    )
    print("Ingestion Complete.")

if __name__ == "__main__":
    if not os.path.exists(PDF_PATH):
        print(f"Error: {PDF_PATH} not found. Please place a PDF in the directory.")
    else:
        # 1. Parse
        print("Starting Dual-Pass Parsing...")
        raw_text = parse_pdf_dual_pass(PDF_PATH)
        
        # 2. Chunk
        print("Chunking text...")
        text_chunks = chunk_text(raw_text)
        
        # 3. Store
        ingest_to_chroma(text_chunks)