import os
import pdfplumber
from pathlib import Path
from typing import Optional


def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    """
    Extract text from a single PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text as string, or None if extraction fails
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        return None

def process_pdf_directory(pdf_dir: str, output_dir: str) -> None:
    """
    Process all PDFs in a directory and save extracted text.
    
    Args:
        pdf_dir: Directory containing PDF files
        output_dir: Directory to save extracted text files
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Get all PDF files
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"No PDF files found in {pdf_dir}")
        return
    
    print(f"Processing {len(pdf_files)} PDF files...")
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        
        # Extract text
        text = extract_text_from_pdf(pdf_path)
        
        if text:
            # Create output filename (replace .pdf with .txt)
            txt_filename = pdf_file.rsplit('.', 1)[0] + '.txt'
            txt_path = os.path.join(output_dir, txt_filename)
            
            # Save extracted text
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            print(f"✓ Extracted: {pdf_file} -> {txt_filename}")
        else:
            print(f"✗ Failed to extract: {pdf_file}")
