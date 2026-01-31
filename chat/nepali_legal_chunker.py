"""
Nepali Civil Code Chunker Module - Integrated for SevaBot

This module provides functionality to parse, clean, and semantically chunk the Nepali Civil Code PDF.
It handles legacy font conversion (Preeti-like), cleans common OCR/conversion artifacts,
and splits the document into logical sections (Dafa) based on Nepali legal structure.

Dependencies:
    - fitz (PyMuPDF)
    - preeti_unicode
"""

import fitz
import preeti_unicode
import re
import uuid
import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class NepaliLegalChunker:
    """
    A class to handle parsing and chunking of Nepali legal documents (specifically Civil Code).
    Optimized for SevaBot RAG system.
    """

    def __init__(self):
        # Compiled patterns for performance
        
        # Chapter pattern: "परिच्छेद" followed by dash/space and Nepali numerals
        # e.g. "परिच्छेद–९"
        self.chapter_pattern = re.compile(r"^\s*परिच्छेद[–-—\s]+([\u0966-\u096F]+)")
        
        # Section pattern: Nepali numerals followed by a dot at the start of a line
        # e.g. "५८८."
        self.section_pattern = re.compile(r"^\s*([\u0966-\u096F]+)\.")
        
        # Dafa pattern: "दफा" followed by space and Nepali numerals
        # e.g. "दफा ५८८"
        self.dafa_pattern = re.compile(r"^\s*दफा\s+([\u0966-\u096F]+)")
        
        # Upa-dafa pattern: "उपदफा" or "(१)", "(२)" etc.
        self.upa_dafa_pattern = re.compile(r"^\s*(?:उपदफा\s+)?\(([\u0966-\u096F]+)\)")

    def is_garbage_line(self, line: str) -> bool:
        """
        Determines if a line is a conversion artifact or noise.
        """
        # Detect the converted URL artifact
        if "धधध।बिधअयफफष्ककष्यल।नयख।लउ" in line:
            return True
        
        # Detect lines that are just a page number (Nepali numerals)
        if re.match(r'^\s*[\u0966-\u096F]+\s*$', line):
            return True
        
        # Detect broken numbering often seen in headers/footers (e.g., "द्दण्घ")
        if re.match(r'^\s*[द्दण्घक्ष्]+\s*$', line):
            return True
            
        # Detect isolated English website text
        if "lawcommission" in line.lower() or "www" in line.lower():
            return True
        
        # Detect very short lines (likely artifacts)
        if len(line.strip()) < 3:
            return True
            
        return False

    def clean_text(self, text: str) -> str:
        """
        Cleans the converted Unicode text by fixing specific font conversion artifacts
        and standardizing Nepali spelling.
        """
        # List of replacements: (incorrect, correct)
        replacements = [
            ("नर्ु", "र्नु"),          # Fix Reph placement: गनर्ु -> गर्नु
            ("नर्े", "र्ने"),          # Fix Reph placement: पनर्े -> पर्ने
            ("कुराह्र", "कुराहरू"),    # Fix plural suffix
            ("ह्र", "हरू"),           # General plural fix
            ("पु¥याएमा", "पुर्याएमा"), # Fix Yen symbol used as Ra
            ("¥", "र्"),             # General Yen -> Ra fix
            (" ः", " :"),            # Fix colon spacing
            ("ः", ":"),              # Normalize colon
            ("व्यत्तिफ", "व्यक्ति"),     # Fix common 'Byakti' typo
            ("आप्फनो", "आफ्नो"),      # Fix 'Aafno'
            ("ाै", "ौ"),             # Fix broken Au matra
            ("एे", "ऐ"),             # Fix Ai matra
            ("अ्र", "अरु"),           # Fix specific typo
            ("लार्इ", "लाई"),         # Fix Lai
            ("ª", "ङ"),              # Fix Nga artifact
            ("Ë", "ङ्ग"),            # Fix Inga/Nga ligature
            ("§", "ट्ट"),            # Fix Tta ligature
            ("æ", """),              # Start quote artifact
            ("Æ", """),              # End quote artifact
            ("दावी", "दाबी"),        # Standardize 'Dabi'
            ("  ", " "),             # Remove double spaces
        ]
        
        for old, new in replacements:
            text = text.replace(old, new)
        
        # --- Advanced Regex Cleaning for Halanta & Artifacts ---
        
        # 1. Remove Halanta if it appears at the end of a word followed by space, 
        #    unless it is a known Sanskritized short word. 
        #    Many PDF extractors leave '् ' at the end of standard words.
        #    Example: "संशोधन् " -> "संशोधन "
        #    (Be careful with legitimate halanta words like 'अर्थात्')
        #    Heuristic: Remove '्' if followed by space/punctuation, unless the word is very short (<3 chars)
        
        def remove_trailing_halanta(match):
            word = match.group(1)
            # List of words that naturally end in halanta (Sanskrit origin)
            keep_halanta = {'अर्थात्', 'सम्भवत्', 'किञ्चित्', 'कदाचित्', 'परिषद्', 'विद्वान्', 'पश्चात्', 'सम्राट्', 'हठात्'}
            if word in keep_halanta:
                return word
            if len(word) < 3: # Keep for short words potentially
                return word
            return word[:-1] # Remove last char (halanta)

        text = re.sub(r'([\u0900-\u097F]+्)(?=[\s,।])', remove_trailing_halanta, text)

        # 2. Fix broken Reph (Ra) placement common in PDF extraction
        #    Pattern: "र्" followed by consonant then vowel sometimes gets split
        #    Specific fix for citizenship "नागरिकता" often appearing as "नागर्ि कता" or similar
        text = text.replace("नागर्ि कता", "नागरिकता")
        text = text.replace("नागर्ि क", "नागरिक")
        
        # 3. Fix Halanta + connector artifacts
        #    Remove ZWJ/ZWNJ if present with Halanta (cleaning invisible chars)
        text = text.replace("\u200d", "").replace("\u200c", "")

        # 4. Context-aware fixes
        text = text.replace("(ª)", "(ङ)")
        
        return text

    def process_pdf_for_rag(
        self, 
        pdf_path: str,
        max_chunk_tokens: int = 800
    ) -> List[Dict]:
        """
        Reads the PDF, extracts text, cleans it, and chunks it for RAG system.
        
        Args:
            pdf_path (str): Path to the input PDF file.
            max_chunk_tokens (int): Maximum tokens per chunk for splitting large sections.
            
        Returns:
            list: A list of dictionaries representing chunks suitable for RAG.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = fitz.open(pdf_path)
        chunks = []
        
        current_chapter = "Unknown"
        current_dafa = "Intro"
        current_upa_dafa = None
        current_text_lines = []
        current_page_idx = 1
        
        logger.info(f"Processing Nepali legal PDF: {pdf_path} ({len(doc)} pages)")
        
        for page_num, page in enumerate(doc):
            try:
                raw_text = page.get_text("text")
                # Convert from Preeti/Legacy font to Unicode
                text = preeti_unicode.convert_text(raw_text)
                # Apply custom cleaning
                text = self.clean_text(text)
            except Exception as e:
                logger.warning(f"Error processing page {page_num+1}: {e}")
                continue
            
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or self.is_garbage_line(line):
                    continue
                
                # Check for Chapter Boundary (परिच्छेद)
                chapter_match = self.chapter_pattern.match(line)
                if chapter_match:
                    # Save the previous accumulated section
                    self._save_chunk_for_rag(
                        chunks, current_text_lines, current_chapter, 
                        current_dafa, current_upa_dafa, current_page_idx, 
                        pdf_path, max_chunk_tokens
                    )
                    
                    # Update state
                    current_chapter = f"परिच्छेद–{chapter_match.group(1)}"
                    current_dafa = "Header"
                    current_upa_dafa = None
                    current_text_lines = [line]
                    current_page_idx = page_num + 1
                    continue
                
                # Check for Dafa Boundary (दफा)
                dafa_match = self.dafa_pattern.match(line)
                if dafa_match:
                    # Save the previous accumulated section
                    self._save_chunk_for_rag(
                        chunks, current_text_lines, current_chapter, 
                        current_dafa, current_upa_dafa, current_page_idx, 
                        pdf_path, max_chunk_tokens
                    )
                    
                    # Update state
                    current_dafa = f"दफा {dafa_match.group(1)}"
                    current_upa_dafa = None
                    current_page_idx = page_num + 1
                    current_text_lines = [line]
                    continue
                
                # Check for Section Boundary (numbered sections)
                section_match = self.section_pattern.match(line)
                if section_match:
                    # Save the previous accumulated section
                    self._save_chunk_for_rag(
                        chunks, current_text_lines, current_chapter, 
                        current_dafa, current_upa_dafa, current_page_idx, 
                        pdf_path, max_chunk_tokens
                    )
                    
                    # Update state
                    current_dafa = f"दफा {section_match.group(1)}"
                    current_upa_dafa = None
                    current_page_idx = page_num + 1
                    current_text_lines = [line]
                    continue
                
                # Check for Upa-dafa Boundary
                upa_dafa_match = self.upa_dafa_pattern.match(line)
                if upa_dafa_match:
                    # Save previous upa-dafa if exists
                    if current_upa_dafa is not None:
                        self._save_chunk_for_rag(
                            chunks, current_text_lines, current_chapter, 
                            current_dafa, current_upa_dafa, current_page_idx, 
                            pdf_path, max_chunk_tokens
                        )
                        current_text_lines = []
                    
                    current_upa_dafa = f"({upa_dafa_match.group(1)})"
                    current_text_lines.append(line)
                    continue
                
                # Append line to current section
                current_text_lines.append(line)

        # Save the final chunk
        self._save_chunk_for_rag(
            chunks, current_text_lines, current_chapter, 
            current_dafa, current_upa_dafa, current_page_idx, 
            pdf_path, max_chunk_tokens
        )
        
        logger.info(f"Extraction complete. Generated {len(chunks)} chunks from Nepali legal document.")
        return chunks

    def _save_chunk_for_rag(
        self, 
        chunks_list: List[Dict], 
        text_lines: List[str], 
        chapter: str,
        dafa: str, 
        upa_dafa: str,
        page: int, 
        source: str,
        max_tokens: int
    ):
        """
        Helper to create and append a chunk optimized for RAG.
        Splits large chunks if they exceed max_tokens.
        """
        if not text_lines:
            return
            
        chunk_text = "\n".join(text_lines).strip()
        if not chunk_text:
            return
        
        # Estimate token count (rough approximation: 1 token ≈ 4 chars for Nepali)
        estimated_tokens = len(chunk_text) // 4
        
        # Build hierarchical title for better context
        title_parts = [chapter]
        if dafa != "Intro" and dafa != "Header":
            title_parts.append(dafa)
        if upa_dafa:
            title_parts.append(upa_dafa)
        hierarchical_title = " > ".join(title_parts)
        
        # If chunk is small enough, save as-is
        if estimated_tokens <= max_tokens:
            chunks_list.append({
                "id": str(uuid.uuid4()),
                "text": chunk_text,
                "metadata": {
                    "chapter": chapter,
                    "dafa": dafa,
                    "upa_dafa": upa_dafa or "",
                    "hierarchical_title": hierarchical_title,
                    "page": page,
                    "source": os.path.basename(source),
                    "chunk_type": "complete_section",
                    "estimated_tokens": estimated_tokens
                }
            })
        else:
            # Split into smaller chunks while preserving context
            self._split_large_chunk(
                chunks_list, chunk_text, chapter, dafa, upa_dafa, 
                hierarchical_title, page, source, max_tokens
            )
    
    def _split_large_chunk(
        self,
        chunks_list: List[Dict],
        text: str,
        chapter: str,
        dafa: str,
        upa_dafa: str,
        hierarchical_title: str,
        page: int,
        source: str,
        max_tokens: int
    ):
        """
        Splits a large chunk into smaller pieces at sentence boundaries.
        """
        # Split by Nepali sentence terminators
        sentences = re.split(r'[।॥]\s*', text)
        
        current_chunk = ""
        chunk_index = 1
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Add terminator back
            sentence += "।"
            
            test_chunk = current_chunk + " " + sentence if current_chunk else sentence
            estimated_tokens = len(test_chunk) // 4
            
            if estimated_tokens > max_tokens and current_chunk:
                # Save current chunk
                chunks_list.append({
                    "id": str(uuid.uuid4()),
                    "text": current_chunk.strip(),
                    "metadata": {
                        "chapter": chapter,
                        "dafa": dafa,
                        "upa_dafa": upa_dafa or "",
                        "hierarchical_title": f"{hierarchical_title} (भाग {chunk_index})",
                        "page": page,
                        "source": os.path.basename(source),
                        "chunk_type": "split_section",
                        "part_number": chunk_index,
                        "estimated_tokens": len(current_chunk) // 4
                    }
                })
                
                chunk_index += 1
                current_chunk = sentence
            else:
                current_chunk = test_chunk
        
        # Save final chunk
        if current_chunk.strip():
            chunks_list.append({
                "id": str(uuid.uuid4()),
                "text": current_chunk.strip(),
                "metadata": {
                    "chapter": chapter,
                    "dafa": dafa,
                    "upa_dafa": upa_dafa or "",
                    "hierarchical_title": f"{hierarchical_title} (भाग {chunk_index})",
                    "page": page,
                    "source": os.path.basename(source),
                    "chunk_type": "split_section",
                    "part_number": chunk_index,
                    "estimated_tokens": len(current_chunk) // 4
                }
            })