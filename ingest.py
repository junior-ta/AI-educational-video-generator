import fitz  #This is PyMuPDF
import pdfplumber
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import io
from PIL import Image
import pytesseract
import platform

# Only set the path if running on Windows (Local)
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# On Linux, The system finds tesseract automatically because we added it to packages.txt.

# Configuration
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "manual_ingest"

def is_inside_bbox(block_bbox, table_bboxes):
    """
    Checks if a text block (block_bbox) is contained within any of the detected table bounding boxes (table_bboxes) using x and y coordainates.
    Refines parsing by ignoring raw text that is actually part of a table. This prevents your AI from reading the table data twice
    """
    bx0, by0, bx1, by1 = block_bbox
    
    for t_bbox in table_bboxes: #for each table box in the list of table boxes
        # extract table coordinates. [pdfplumber format: (x0, top, x1, bottom)]
        tx0, ty0, tx1, ty1 = t_bbox
        
        # Check if the text block is mostly inside the table)
        if (bx0 >= tx0 and bx1 <= tx1 and by0 >= ty0 and by1 <= ty1):
            return True
    return False

def extract_text_from_images(fitz_page):
    """
    Pass 3: OCR (Optical Character Recognition)
    Extracts images from the page, converts them to text, and returns the text.
    """
    image_text = ""
    # get_images returns list of [xref, smask, width, height, bpc, colorspace, ...]
    image_list = fitz_page.get_images(full=True)
    
    if not image_list:
        return ""
        
    print(f"   - Found {len(image_list)} images on page. Running OCR...")

    for img_index, img in enumerate(image_list):
        xref = img[0]
        # extract_image returns a dictionary with metadata and the raw byte stream
        base_image = fitz_page.parent.extract_image(xref)
        image_bytes = base_image["image"]
        
        # Load image into memory for analysis using Pillow
        try:
            image = Image.open(io.BytesIO(image_bytes))
            
            # Run Tesseract OCR on the PIL Image object
            text = pytesseract.image_to_string(image)
            
            # Clean up: only add if we found significant text (avoids noise from icons/logos)
            if len(text.strip()) > 5:
                image_text += f"\n[IMAGE OCR CONTENT]:\n{text}\n"
                
        except Exception as e:
            print(f"OCR Error on image {img_index}: {e}")
            
    return image_text

def parse_pdf_dual_pass(file_bytes):
    """
    first pass: Use pdfplumber to extract tables and their coordinates. 
        Stored as a list of (y-coordinates, markdown table content) in tables_data
    second pass: Use PyMuPDF to extract text blocks, and use is_inside_bbox to filter out those inside tables.
        Stored as a list of (y-coordiantes, text) in text_data
    Merge: Combine text and markdown tables based on vertical position (reading order).
    """
    print(f"Parsing files...")
    full_text = ""
    
    # Open with both libraries
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as plumber_pdf, fitz.open(stream=file_bytes, filetype="pdf") as fitz_pdf:
            
            for page_num, plumber_page in enumerate(plumber_pdf.pages): #iterating each page
                if page_num >= len(fitz_pdf): break # Safety check

                fitz_page = fitz_pdf[page_num]
                
                # --- First Pass: Table Extraction with pdfplumber ---
                tables = plumber_page.find_tables()
                table_data = [] #will store tuples of tables data (y-coordinate, content of the table)
                table_bboxes = []

                for table in tables:
                    # Get the bounding box of the table
                    table_bboxes.append(table.bbox)
                    
                    # Extract table content and convert to Markdown
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
                    
                    # Store (y-coordinate [using top y-coordinate (table.bbox[1]) to place it in the stream], content) for sorting later
                    table_data.append((table.bbox[1], markdown_table))



                # --- Second Pass: Text Extraction with PyMuPDF ---
                # 'blocks' returns a list of items: (x0, y0, x1, y1, "text", block_no, block_type)
                text_blocks = fitz_page.get_text("blocks")
                text_data = []

                for block in text_blocks:
                    block_bbox = block[:4] # block[4] is the text content
                    block_text = block[4] #the text content

                    # Filter: If this text block is actually inside a table, ignore it (because we already captured it as a Markdown table above)
                    if not is_inside_bbox(block_bbox, table_bboxes):
                        # Store (y-coordinate, content)
                        text_data.append((block_bbox[1], block_text))

                # --- Third Pass: Images ---
                ocr_text = extract_text_from_images(fitz_page)

                # --- MERGE & SORT ---
                # Combine tables and text
                all_content = table_data + text_data
                
                # Sort by vertical position (y0) to maintain reading order
                all_content.sort(key=lambda x: x[0])
                
                # Join into a single string for the page
                page_content = "\n".join([item[1] for item in all_content]) #each line is teh data part of a table or text tuple
                full_text += f"\n--- Page {page_num + 1} ---\n{page_content}"


    except Exception as e:
        print (f"Erro parsing: {e}")
        return None
    
    return full_text

def chunk_text(text):
    """
    Split text into manageable chunks with overlap to maintain context.
    """

    #This is standard for AI. I try to split by paragraphs first (\n\n), then lines (\n), then words
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_text(text)
    
    return chunks

def ingest_to_chroma(chunks, filename, client):
    """
    Ingests chunks into ChromaDB.
    ARGS:
      filename: Used for metadata so we know WHICH file the text came from.
      client: The active ChromaDB client passed from the main loop.
    """

    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    # Create distinct IDs based on filename and chunk index (Clean filename to be safe for IDs)
    safe_name = os.path.basename(filename).replace(" ", "_")
    ids = [f"{safe_name}_chunk_{i}" for i in range(len(chunks))]
    
    # include the filename in the Metadata
    metadatas = [{"source": filename} for _ in chunks]
    
    collection.add(
        documents=chunks,
        metadatas=metadatas,
        ids=ids
    )

def process_uploaded_files(uploaded_files):
    """
   for Streamlit function to pass a list of UploadedFile objects.
    """

    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    
    status_log = []

    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name
        file_bytes = uploaded_file.getvalue()
        
        # status_log.append(f"Processing {file_name}...")
        
        # Parse (using the new bytes-compatible function)
        raw_text = parse_pdf_dual_pass(file_bytes)
        
        if raw_text:
            chunks = chunk_text(raw_text)
            ingest_to_chroma(chunks, file_name, chroma_client)
            status_log.append(f"Successfully ingested {file_name} ({len(chunks)} chunks).")
        else:
            status_log.append(f"Failed to parse {file_name}.")
            
    return status_log



# def main():
#     if not os.path.exists(SOURCE_DIRECTORY):
#         os.makedirs(SOURCE_DIRECTORY)
#         print(f"Created directory {SOURCE_DIRECTORY}. Please put PDF files there and run again.")
#         return

#     # Initialize Client ONCE (more efficient)
#     chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

#     # 2. Find all PDFs
#     pdf_files = glob.glob(os.path.join(SOURCE_DIRECTORY, "*.pdf"))
    
#     if not pdf_files:
#         print(f"No PDFs found in {SOURCE_DIRECTORY}")
#         return

#     print(f"Found {len(pdf_files)} Documents.")

#     # 3. Process each file
#     for pdf_file in pdf_files:
#         print(f"--- Processing {os.path.basename(pdf_file)} ---")
        
#         # Parse
#         raw_text = parse_pdf_dual_pass(pdf_file)
        
#         if raw_text:
#             chunks = chunk_text(raw_text)
            
#             # Save in database
#             ingest_to_chroma(chunks, os.path.basename(pdf_file), chroma_client)
        
#         print(f"Finished {os.path.basename(pdf_file)}\n")

#     print("All documents processed.")

# if __name__ == "__main__":
#     main()