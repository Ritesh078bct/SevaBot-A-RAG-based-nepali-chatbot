"""
RAG Service for Nepali Legal Documents
Handles document parsing, chunking, embedding, and retrieval.
"""

import os
import logging
from typing import List, Dict, Tuple
from pathlib import Path
import re
import json

# LlamaParse for PDF parsing
from llama_parse import LlamaParse

# Embeddings
from sentence_transformers import SentenceTransformer

# Vector database
import chromadb
from chromadb.config import Settings

# Token counting
import tiktoken

from django.conf import settings

logger = logging.getLogger(__name__)


class NepaliRAGService:
    """
    Service class for handling RAG operations on Nepali legal documents.
    """
    
    def __init__(self):
        # Initialize LlamaParse
        self.parser = LlamaParse(
            api_key=settings.LLAMAPARSE_API_KEY,
            result_type="markdown",  # Get structured markdown output
            language="hi",  # Hindi/Nepali support
            verbose=True
        )
        
        # Initialize embedding model
        # This model requires prefixes for optimal performance
        logger.info("Loading multilingual-e5-large embedding model...")
        self.embedding_model = SentenceTransformer('intfloat/multilingual-e5-large')
        logger.info("Embedding model loaded successfully")
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=str(settings.CHROMADB_PATH),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Token counter for chunking
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Chunking parameters
        self.chunk_size = 650  # Target tokens per chunk
        self.chunk_overlap = 65  # 10% overlap
        
    def parse_pdf(self, pdf_path: str) -> Tuple[str, Dict]:
        """
        Parse PDF using LlamaParse with structural preservation.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Tuple of (markdown_text, metadata)
        """
        logger.info(f"Parsing PDF: {pdf_path}")
        
        try:
            # Parse the document
            documents = self.parser.load_data(pdf_path)
            
            # LlamaParse returns a list of Document objects
            # Combine them into one markdown string
            markdown_text = "\n\n".join([doc.text for doc in documents])
            
            metadata = {
                'num_pages': len(documents),
                'total_chars': len(markdown_text),
            }
            
            logger.info(f"Parsed {metadata['num_pages']} pages, {metadata['total_chars']} characters")
            
            return markdown_text, metadata
            
        except Exception as e:
            logger.error(f"PDF parsing failed: {str(e)}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string."""
        return len(self.tokenizer.encode(text))
    
    def semantic_chunk_markdown(self, markdown_text: str) -> List[Dict]:
        """
        Chunk markdown text using semantic boundaries (headers, paragraphs).
        Preserves legal document structure (sections, articles).
        
        Args:
            markdown_text: Full markdown text from PDF
            
        Returns:
            List of chunks with metadata
        """
        logger.info("Starting semantic chunking...")
        
        # Split by major sections (headers)
        # Legal documents often use # Section, ## Article, ### Subsection
        sections = re.split(r'\n(#{1,3}\s+.+?)\n', markdown_text)
        
        chunks = []
        current_chunk = ""
        current_metadata = {
            'section': '',
            'subsection': ''
        }
        
        for i, section in enumerate(sections):
            # Check if this is a header
            if section.startswith('#'):
                # Determine header level
                header_level = len(section.split()[0])
                header_text = section.replace('#', '').strip()
                
                if header_level == 1:
                    current_metadata['section'] = header_text
                    current_metadata['subsection'] = ''
                elif header_level == 2:
                    current_metadata['subsection'] = header_text
                
                # Add header to current chunk
                current_chunk += f"\n{section}\n"
                
            else:
                # This is content, not a header
                # Split into paragraphs
                paragraphs = section.split('\n\n')
                
                for paragraph in paragraphs:
                    if not paragraph.strip():
                        continue
                    
                    # Check if adding this paragraph exceeds chunk size
                    test_chunk = current_chunk + "\n\n" + paragraph
                    token_count = self.count_tokens(test_chunk)
                    
                    if token_count > self.chunk_size and current_chunk:
                        # Save current chunk
                        chunks.append({
                            'text': current_chunk.strip(),
                            'metadata': current_metadata.copy(),
                            'token_count': self.count_tokens(current_chunk)
                        })
                        
                        # Start new chunk with overlap
                        # Keep last paragraph for context
                        overlap_text = self._get_overlap(current_chunk)
                        current_chunk = overlap_text + "\n\n" + paragraph
                    else:
                        current_chunk += "\n\n" + paragraph
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append({
                'text': current_chunk.strip(),
                'metadata': current_metadata.copy(),
                'token_count': self.count_tokens(current_chunk)
            })
        
        logger.info(f"Created {len(chunks)} semantic chunks")
        
        return chunks
    
    def _get_overlap(self, text: str) -> str:
        """
        Get the last portion of text for overlap.
        Tries to break at sentence boundaries.
        """
        target_tokens = self.chunk_overlap
        sentences = re.split(r'([।॥।\.\?\!])', text)
        
        # Reconstruct sentences from the end
        overlap = ""
        for i in range(len(sentences) - 1, -1, -1):
            test_overlap = sentences[i] + overlap
            if self.count_tokens(test_overlap) > target_tokens:
                break
            overlap = test_overlap
        
        return overlap.strip()
    
    def generate_embeddings(self, chunks: List[Dict]) -> List[List[float]]:
        """
        Generate embeddings for text chunks using multilingual-e5-large.
        
        IMPORTANT: This model requires "passage: " prefix for documents.
        
        Args:
            chunks: List of chunk dictionaries
            
        Returns:
            List of embedding vectors
        """
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        
        # Prefix all chunks with "passage: " for optimal retrieval
        texts = [f"passage: {chunk['text']}" for chunk in chunks]
        
        # Generate embeddings in batches
        embeddings = self.embedding_model.encode(
            texts,
            batch_size=8,
            show_progress_bar=True,
            normalize_embeddings=True  # Important for cosine similarity
        )
        
        logger.info("Embeddings generated successfully")
        
        return embeddings.tolist()
    
    def store_in_chromadb(
        self, 
        collection_name: str,
        chunks: List[Dict],
        embeddings: List[List[float]],
        document_metadata: Dict
    ) -> str:
        """
        Store chunks and embeddings in ChromaDB.
        
        Args:
            collection_name: Name for the ChromaDB collection
            chunks: List of text chunks with metadata
            embeddings: List of embedding vectors
            document_metadata: Document-level metadata
            
        Returns:
            Collection ID
        """
        logger.info(f"Storing embeddings in ChromaDB collection: {collection_name}")
        
        try:
            # Get or create collection
            collection = self.chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "description": "Nepali legal documents",
                    **document_metadata
                }
            )
            
            # Prepare data for insertion
            ids = [f"{collection_name}_chunk_{i}" for i in range(len(chunks))]
            documents = [chunk['text'] for chunk in chunks]
            metadatas = [
                {
                    **chunk['metadata'],
                    'token_count': chunk['token_count'],
                    'chunk_index': i,
                    **document_metadata
                }
                for i, chunk in enumerate(chunks)
            ]
            
            # Upsert into ChromaDB
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            
            logger.info(f"Successfully stored {len(chunks)} chunks in ChromaDB")
            
            return collection.name
            
        except Exception as e:
            logger.error(f"ChromaDB storage failed: {str(e)}")
            raise
    
    def retrieve_context(
        self, 
        query: str, 
        collection_name: str,
        top_k: int = 5
    ) -> List[Dict]:
        """
        Retrieve relevant context for a query using semantic search.
        
        IMPORTANT: Query must be prefixed with "query: " for optimal retrieval.
        
        Args:
            query: User's question
            collection_name: ChromaDB collection to search
            top_k: Number of chunks to retrieve
            
        Returns:
            List of relevant chunks with metadata
        """
        logger.info(f"Retrieving context for query: {query[:100]}...")
        
        try:
            # Get collection
            collection = self.chroma_client.get_collection(name=collection_name)
            
            # Generate query embedding with "query: " prefix
            query_embedding = self.embedding_model.encode(
                f"query: {query}",
                normalize_embeddings=True
            ).tolist()
            
            # Query ChromaDB
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )
            
            # Format results
            context_chunks = []
            if results['documents']:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    context_chunks.append({
                        'text': doc,
                        'metadata': metadata,
                        'relevance_score': 1 - distance,  # Convert distance to similarity
                        'rank': i + 1
                    })
            
            logger.info(f"Retrieved {len(context_chunks)} relevant chunks")
            
            return context_chunks
            
        except Exception as e:
            logger.error(f"Context retrieval failed: {str(e)}")
            return []
    
    def format_rag_prompt(self, query: str, context_chunks: List[Dict]) -> str:
        """
        Format the RAG prompt for the LLM with Nepali-specific instructions.
        
        Args:
            query: User's question
            context_chunks: Retrieved context chunks
            
        Returns:
            Formatted prompt string
        """
        # Combine context chunks
        context = "\n\n---\n\n".join([
            f"[स्रोत {chunk['rank']}]\n{chunk['text']}"
            for chunk in context_chunks
        ])
        
        prompt = f"""तपाईं एक नेपाली कानुनी सहायक हुनुहुन्छ। तलको सन्दर्भको आधारमा मात्र प्रश्नको उत्तर दिनुहोस्।

सन्दर्भ (Context):
{context}

प्रश्न (Question): {query}

निर्देशन (Instructions):
1. माथि दिइएको सन्दर्भको आधारमा मात्र उत्तर दिनुहोस्
2. उत्तर नेपालीमा दिनुहोस्
3. यदि सन्दर्भमा जानकारी छैन भने "मलाई यो जानकारी उपलब्ध छैन" भन्नुहोस्
4. कुन स्रोतबाट जानकारी लिनुभयो त्यो उल्लेख गर्नुहोस् (जस्तै: [स्रोत 1] अनुसार...)
5.दिइएका स्रोतहरूका लेखाइमा त्रुटि हुनसक्ने सम्भावना भएकाले अन्त्यमा तपाईं आफ्नो उत्तर पनि अलगै लेखिदिनुहोस्।

उत्तर (Answer):"""
        
        return prompt
    
    def process_document(
        self,
        pdf_path: str,
        document_id: int,
        user_id: int
    ) -> Dict:
        """
        Full pipeline: Parse -> Chunk -> Embed -> Store
        
        Args:
            pdf_path: Path to PDF file
            document_id: Database document ID
            user_id: User ID for collection naming
            
        Returns:
            Processing results dictionary
        """
        try:
            # Step 1: Parse PDF
            markdown_text, parse_metadata = self.parse_pdf(pdf_path)
            
            # Step 2: Chunk the text
            chunks = self.semantic_chunk_markdown(markdown_text)
            
            # Step 3: Generate embeddings
            embeddings = self.generate_embeddings(chunks)
            
            # Step 4: Store in ChromaDB
            collection_name = f"user_{user_id}_doc_{document_id}"
            self.store_in_chromadb(
                collection_name=collection_name,
                chunks=chunks,
                embeddings=embeddings,
                document_metadata={
                    'user_id': user_id,
                    'document_id': document_id,
                    'filename': Path(pdf_path).name
                }
            )
            
            return {
                'success': True,
                'collection_id': collection_name,
                'num_pages': parse_metadata['num_pages'],
                'num_chunks': len(chunks),
                'total_tokens': sum(chunk['token_count'] for chunk in chunks)
            }
            
        except Exception as e:
            logger.error(f"Document processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }