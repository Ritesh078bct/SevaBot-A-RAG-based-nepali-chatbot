"""
SevaBot: Legal-Grade RAG Service for Nepali
Enhanced with custom Nepali legal chunker for Preeti font documents.
"""

import os
import logging
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import re
import json
from datetime import datetime

# Custom Nepali chunker for legacy documents
from .nepali_legal_chunker import NepaliLegalChunker

# Embeddings
from sentence_transformers import SentenceTransformer

# Vector database
import chromadb
from chromadb.config import Settings

# NLP utilities
import tiktoken
import numpy as np

from django.conf import settings

logger = logging.getLogger(__name__)


class SevaBot_RAG_Service:
    """
    Professional RAG service for Nepali legal documents.
    Uses custom Nepali chunker for all documents to ensure consistent handling of legal structures.
    """
    
    # Collection names
    PERMANENT_COLLECTION = "sevabot_permanent_knowledge"
    USER_COLLECTION_PREFIX = "sevabot_user"
    
    def __init__(self):
        """Initialize SevaBot RAG service."""
        
        # Initialize custom Nepali legal chunker
        # Used for all documents (both Preeti and Unicode) to ensure consistent
        # handling of legal sections (Dafa, Upadafa, etc.)
        self.nepali_chunker = NepaliLegalChunker()
        
        # Initialize embedding model
        # Using a model that supports multilingual semantic search
        logger.info("Loading multilingual-e5-large for Nepali embeddings...")
        self.embedding_model = SentenceTransformer(
            'intfloat/multilingual-e5-large',
            device='cpu'
        )
        self.embedding_model.max_seq_length = 512
        logger.info("Embedding model loaded successfully")
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=str(settings.CHROMADB_PATH),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False
            )
        )
        
        # Token counter
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Initialize collections
        self._initialize_permanent_collection()
    
    def _initialize_permanent_collection(self):
        """Initialize the permanent knowledge base collection."""
        try:
            self.permanent_collection = self.chroma_client.get_or_create_collection(
                name=self.PERMANENT_COLLECTION,
                metadata={
                    "description": "SevaBot Permanent Knowledge Base - Nepali Legal Codes",
                    "type": "permanent",
                    "created_at": datetime.now().isoformat()
                }
            )
            logger.info(f"Permanent collection initialized: {self.permanent_collection.count()} documents")
        except Exception as e:
            logger.error(f"Failed to initialize permanent collection: {str(e)}")
            raise
            
    def process_document(
        self, 
        pdf_path: str,
        document_id: int,
        user_id: int,
        add_to_permanent_kb: bool = False
    ) -> Dict:
        """
        Process a document using the Nepali legal chunker.
        
        Args:
            pdf_path: Path to the PDF file
            document_id: Database ID of the document
            user_id: ID of the user who uploaded
            add_to_permanent_kb: Whether to add to shared permanent KB
            
        Returns:
            Dict with processing stats
        """
        logger.info(f"Processing document: {pdf_path}")
        
        try:
            # 1. Chunk the document
            chunks = self.nepali_chunker.process_pdf_for_rag(
                pdf_path=pdf_path,
                max_chunk_tokens=800
            )
            
            logger.info(f"Generated {len(chunks)} chunks")
            
            if not chunks:
                msg = "No text chunks could be extracted from the document. The PDF might be empty, corrupted (zlib error), or image-based without text layer."
                logger.warning(msg)
                return {
                    'success': False,
                    'error': msg
                }
            
            # 2. Generate embeddings
            embeddings = self.generate_embeddings_with_prefix(chunks, "passage")
            
            # 3. Store in appropriate collection
            if add_to_permanent_kb:
                # Store in permanent KB
                # Note: This usually requires admin rights or specific logic
                collection_name = self.PERMANENT_COLLECTION
                
                doc_prefix = Path(pdf_path).stem.replace(" ", "_")
                ids = [chunk.get('id', f"{doc_prefix}_{document_id}_chunk_{i}") for i, chunk in enumerate(chunks)]
                documents = [chunk['text'] for chunk in chunks]
                metadatas = [
                    {
                        **chunk['metadata'],
                        'collection_type': 'permanent',
                        'knowledge_category': 'legal_code',
                        'parser_type': 'nepali_legal_chunker',
                        'document_id': str(document_id),
                        'source_file': Path(pdf_path).name
                    }
                    for chunk in chunks
                ]
                
                self.permanent_collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas
                )
                
            else:
                # Store in user-specific temporary collection
                collection_name = self.store_in_user_collection(
                    user_id=user_id,
                    document_id=document_id,
                    chunks=chunks,
                    embeddings=embeddings,
                    document_metadata={
                        'filename': Path(pdf_path).name,
                        'processed_at': datetime.now().isoformat(),
                        'parser_used': 'nepali_legal_chunker',
                        'pdf_type': 'auto_detected'
                    }
                )
            
            return {
                'success': True,
                'collection_id': collection_name,
                'num_chunks': len(chunks),
                'num_pages': chunks[-1]['metadata'].get('page_end', 0) if chunks else 0,
                'parsing_method': 'nepali_legal_chunker'
            }
            
        except Exception as e:
            logger.error(f"Document processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))
    
    def generate_embeddings_with_prefix(
        self, 
        chunks: List[Dict],
        prefix_type: str = "passage"
    ) -> List[List[float]]:
        """
        Generate embeddings with proper prefixing for E5 model.
        
        Args:
            chunks: List of text chunks
            prefix_type: Either "passage" or "query"
            
        Returns:
            List of embedding vectors
        """
        logger.info(f"Generating embeddings with '{prefix_type}:' prefix for {len(chunks)} chunks...")
        
        # Prefix all texts according to E5 requirements
        texts = [f"{prefix_type}: {chunk['text']}" for chunk in chunks]
        
        # Generate embeddings in batches
        embeddings = self.embedding_model.encode(
            texts,
            batch_size=8,
            show_progress_bar=True,
            normalize_embeddings=True,
            convert_to_numpy=True
        )
        
        logger.info("Embeddings generated with proper prefixing")
        
        return embeddings.tolist()
    
    def store_in_user_collection(
        self,
        user_id: int,
        document_id: int,
        chunks: List[Dict],
        embeddings: List[List[float]],
        document_metadata: Dict
    ) -> str:
        """
        Store user-uploaded document in dedicated collection.
        """
        collection_name = f"{self.USER_COLLECTION_PREFIX}_{user_id}_doc_{document_id}"
        
        logger.info(f"Storing in user collection: {collection_name}")
        
        try:
            collection = self.chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "description": f"User {user_id} document {document_id}",
                    "type": "user_uploaded",
                    "user_id": str(user_id),
                    "document_id": str(document_id),
                    **document_metadata
                }
            )
            
            # Prepare data
            ids = [chunk.get('id', f"chunk_{i}") for i, chunk in enumerate(chunks)]
            documents = [chunk['text'] for chunk in chunks]
            metadatas = [
                {
                    **chunk['metadata'],
                    'chunk_index': i,
                    'collection_type': 'user'
                }
                for i, chunk in enumerate(chunks)
            ]
            
            # Upsert
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            
            logger.info(f"Stored {len(chunks)} chunks in user collection")
            
            return collection_name
            
        except Exception as e:
            logger.error(f"Failed to store in user collection: {str(e)}")
            raise
    
    def load_permanent_knowledge(
        self,
        knowledge_dir: Path,
        force_reload: bool = False
    ):
        """
        Load permanent knowledge base from directory.
        Supports incremental loading (skips already processed files).
        """
        if force_reload:
            logger.warning("Force reloading permanent collection...")
            self.chroma_client.delete_collection(self.PERMANENT_COLLECTION)
            self._initialize_permanent_collection()
        
        logger.info(f"Loading permanent knowledge from: {knowledge_dir}")
        
        pdf_files = list(knowledge_dir.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        # Get list of already processed files
        existing_files = set()
        if not force_reload and self.permanent_collection.count() > 0:
            # Efficiently query just the source_file metadata
            try:
                # Chroma doesn't support "distinct" easily, so we might fetch a subset or just assume
                # simpler check: if we can't easily get list, we just process.
                # But better: query all metadata? No, too heavy.
                # Strategy: for each file, check if it exists in DB.
                pass 
            except Exception:
                pass

        for pdf_file in pdf_files:
            try:
                # Check if file is already processed
                if not force_reload:
                    # Check if any chunk from this file exists
                    existing = self.permanent_collection.get(
                        where={"source_file": pdf_file.name},
                        limit=1
                    )
                    if existing['ids']:
                        logger.info(f"Skipping {pdf_file.name} (already processed)")
                        continue
                
                logger.info(f"Processing permanent knowledge: {pdf_file.name}")
                
                # Use standard process_document logic but add to permanent KB
                # We simulate a doc ID for file tracking
                self.process_document(
                    pdf_path=str(pdf_file),
                    document_id=abs(hash(pdf_file.name)) % 100000, # Simple deterministic ID
                    user_id=0, # System user
                    add_to_permanent_kb=True
                )
                
            except Exception as e:
                logger.error(f"Failed to load {pdf_file.name}: {str(e)}")
        
        logger.info(f"Permanent collection loaded: {self.permanent_collection.count()} total chunks")

    def retrieve_context(
        self,
        query: str,
        collection_name: Optional[str] = None,
        top_k: int = 5,
        use_permanent_kb: bool = False
    ) -> List[Dict]:
        """
        Retrieve relevant context for a query.
        
        Args:
            query: User question
            collection_name: Name of specific user collection to search (optional)
            top_k: Number of chunks to retrieve
            use_permanent_kb: Whether to also search the permanent knowledge base
            
        Returns:
            List of relevant chunks with scores
        """
        results = []
        
        # Generate query embedding
        # Note: E5 instruction says to use "query: " prefix for asymmetric tasks
        query_embedding = self.embedding_model.encode(
            [f"query: {query}"],
            normalize_embeddings=True,
            convert_to_numpy=True
        )[0].tolist()
        
        # 1. Search user collection if specified
        if collection_name:
            try:
                collection = self.chroma_client.get_collection(collection_name)
                user_results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    include=['documents', 'metadatas', 'distances']
                )
                
                # Process results
                if user_results['ids'] and user_results['ids'][0]:
                    for i, doc_id in enumerate(user_results['ids'][0]):
                        distance = user_results['distances'][0][i]
                        # Convert cosine distance to similarity score
                        # Chroma returns distance (0 = identical, 2 = opposite)
                        # Similarity approx 1 - (distance / 2)
                        similarity = 1 - (distance / 2)
                        
                        results.append({
                            'id': doc_id,
                            'text': user_results['documents'][0][i],
                            'metadata': user_results['metadatas'][0][i],
                            'relevance_score': similarity,
                            'source': 'user_document'
                        })
            except Exception as e:
                logger.warning(f"Failed to query user collection {collection_name}: {e}")

        # 2. Search permanent KB if requested
        if use_permanent_kb:
            try:
                kb_results = self.permanent_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    include=['documents', 'metadatas', 'distances']
                )
                
                if kb_results['ids'] and kb_results['ids'][0]:
                    for i, doc_id in enumerate(kb_results['ids'][0]):
                        distance = kb_results['distances'][0][i]
                        similarity = 1 - (distance / 2)
                        
                        results.append({
                            'id': doc_id,
                            'text': kb_results['documents'][0][i],
                            'metadata': kb_results['metadatas'][0][i],
                            'relevance_score': similarity,
                            'source': 'permanent_kb'
                        })
            except Exception as e:
                logger.warning(f"Failed to query permanent collection: {e}")
        
        # Sort combined results by relevance
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Return unique results (deduplicate by text content) used seen set
        seen_texts = set()
        unique_results = []
        
        for r in results:
            # Hash text for simpler deduplication
            text_hash = hash(r['text'])
            if text_hash not in seen_texts:
                seen_texts.add(text_hash)
                unique_results.append(r)
        
        # Return requested number of top results
        return unique_results[:top_k]

    def format_rag_prompt(self, query: str, chunks: List[Dict]) -> str:
        """
        Format a RAG prompt for the LLM.
        
        Args:
            query: User question
            chunks: Retrieved context chunks
            
        Returns:
            Formatted prompt string
        """
        context_str = ""
        
        for i, chunk in enumerate(chunks):
            source_info = chunk.get('metadata', {}).get('section', 'Unknown Section')
            if 'source_file' in chunk.get('metadata', {}):
                 source_info += f" ({chunk['metadata']['source_file']})"
            
            context_str += f"""
[सन्दर्भ {i+1} - {source_info}]
{chunk['text']}
"""
            
        prompt = f"""तपाईं एक दक्ष नेपाली कानुनी सहायक (SevaBot) हुनुहुन्छ। तल दिइएका "मुलुकी देवानी संहिता" वा अन्य कानुनी दस्तावेजका सन्दर्भहरू प्रयोग गरी सोधिएको प्रश्नको स्पष्ट र सटिक उत्तर दिनुहोस्।

नियमहरू:
१. दिइएको सन्दर्भमा आधारित भएर मात्र उत्तर दिनुहोस्।
२. यदि सन्दर्भमा उत्तर छैन भने, "दिइएको जानकारीमा यो प्रश्नको उत्तर भेटिएन" भनेर भन्नुहोस्।
३. कानुनी दफा र उपदफाहरूको सही उल्लेख गर्नुहोस्।
४. उत्तर शुद्ध नेपाली भाषामा हुनुपर्छ।

सन्दर्भ सामग्री:
{context_str}

प्रश्न: {query}

उत्तर:"""
        return prompt

# Alias for compatibility
NepaliRAGService = SevaBot_RAG_Service