"""
RAG (Retrieval-Augmented Generation) system for PartSelect repair data.
Uses FAISS for vector search and SentenceTransformers for embeddings.
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import sys

# Set up logging - NO STDOUT to avoid MCP protocol corruption
logging.basicConfig(
    level=logging.DEBUG,  # More verbose logging
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rag_system.log'),
        logging.FileHandler('server_debug.log')  # Also log to server debug
    ]
)

try:
    import faiss
    from sentence_transformers import SentenceTransformer
    RAG_AVAILABLE = True
    print("RAG dependencies imported successfully")
except ImportError as e:
    RAG_AVAILABLE = False
    faiss = None
    SentenceTransformer = None
    print(f"RAG dependencies import failed: {e}")
    print("Install with: pip install faiss-cpu sentence-transformers")

logger = logging.getLogger(__name__)

class RepairRAGSystem:
    def __init__(self, data_dir: str = "data", model_name: str = "intfloat/e5-small-v2"):
        print(f"Initializing RepairRAGSystem")
        print(f"   Data directory: {data_dir}")
        print(f"   Model: {model_name}")
        
        self.data_dir = Path(data_dir)
        self.model_name = model_name
        self.index_dir = Path(".rag_index")
        
        print(f"   Creating index directory: {self.index_dir.absolute()}")
        self.index_dir.mkdir(exist_ok=True)
        
        self.index_file = self.index_dir / "repairs.faiss"
        self.meta_file = self.index_dir / "repairs.meta.json"
        
        print(f"   Index file: {self.index_file}")
        print(f"   Meta file: {self.meta_file}")
        
        self._model = None
        self._index = None
        self._metadata = []
        
        if not RAG_AVAILABLE:
            print("RAG dependencies not available. Install: pip install faiss-cpu sentence-transformers")
        else:
            print("RAG dependencies are available")
    
    def _load_model(self):
        """Load the sentence transformer model"""
        if not RAG_AVAILABLE:
            error_msg = "RAG dependencies not installed"
            logger.error(f"❌ {error_msg}")
            raise ImportError(error_msg)
        
        if self._model is None:
            logger.info(f"🤖 Loading SentenceTransformer model: {self.model_name}")
            logger.info("   This may take a while on first run (downloading model)...")
            try:
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"✅ Model loaded successfully: {self.model_name}")
            except Exception as e:
                logger.error(f"❌ Failed to load model {self.model_name}: {e}")
                raise
        else:
            logger.debug(f"📋 Model already loaded: {self.model_name}")
        return self._model
    
    def _should_rebuild_index(self) -> bool:
        """Check if index needs to be rebuilt based on data freshness"""
        try:
            # If index files don't exist, rebuild
            if not self.index_file.exists() or not self.meta_file.exists():
                logger.info("🔄 Index files don't exist, rebuild needed")
                return True
            
            # Load metadata to check data hash
            with open(self.meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            # Calculate current data hash
            current_hash = self._calculate_data_hash()
            cached_hash = meta.get('data_hash', '')
            
            if current_hash != cached_hash:
                logger.info(f"🔄 Data changed (hash mismatch), rebuild needed")
                logger.info(f"   Cached: {cached_hash[:16]}...")
                logger.info(f"   Current: {current_hash[:16]}...")
                return True
            
            logger.info("✅ Index is up-to-date, using cache")
            return False
            
        except Exception as e:
            logger.warning(f"⚠️ Error checking cache freshness: {e}, rebuilding")
            return True
    
    def _calculate_data_hash(self) -> str:
        """Calculate hash of all data files to detect changes"""
        hash_md5 = hashlib.md5()
        
        # Get all JSON files in data directory
        json_files = sorted(self.data_dir.rglob("*.json"))
        
        for json_file in json_files:
            try:
                # Add file path and modification time to hash
                hash_md5.update(str(json_file).encode('utf-8'))
                hash_md5.update(str(json_file.stat().st_mtime).encode('utf-8'))
                
                # Add file content to hash
                with open(json_file, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_md5.update(chunk)
            except Exception as e:
                logger.warning(f"⚠️ Error hashing {json_file}: {e}")
        
        return hash_md5.hexdigest()
    
    def _embed_texts(self, texts: List[str]) -> Any:
        """Generate embeddings for texts"""
        model = self._load_model()
        # For e5 models, prefix with "passage: " for documents, "query: " for queries
        passages = [f"passage: {text}" for text in texts]
        return model.encode(passages, normalize_embeddings=True)
    
    def _embed_query(self, query: str) -> Any:
        """Generate embedding for a query"""
        model = self._load_model()
        return model.encode([f"query: {query}"], normalize_embeddings=True)[0]
    
    def _hash_text(self, text: str) -> str:
        """Generate a hash for text deduplication"""
        return hashlib.sha256(text.encode()).hexdigest()[:12]
    
    def _extract_repair_sections(self, json_file: Path) -> List[Dict[str, Any]]:
        """Extract repair sections from JSON files"""
        try:
            data = json.loads(json_file.read_text(encoding='utf-8'))
            
            # Determine appliance type from file path
            appliance_type = "General"
            if "refrigerator" in str(json_file).lower():
                appliance_type = "Refrigerator"
            elif "dishwasher" in str(json_file).lower():
                appliance_type = "Dishwasher"
            elif "washer" in str(json_file).lower():
                appliance_type = "Washer"
            elif "dryer" in str(json_file).lower():
                appliance_type = "Dryer"
            
            sections = []
            
            # Handle repair sections (detailed symptom files)
            if "repair_sections" in data:
                symptom_title = data.get("symptom_title", "")
                for section in data["repair_sections"]:
                    # Create comprehensive text for embedding
                    text_parts = []
                    
                    if symptom_title:
                        text_parts.append(f"Symptom: {symptom_title}")
                    
                    text_parts.append(f"Issue: {section.get('title', '')}")
                    text_parts.append(f"Description: {section.get('description', '')}")
                    
                    # Add instructions
                    instructions = section.get('instructions', [])
                    if instructions:
                        text_parts.append("Instructions: " + " | ".join(instructions))
                    
                    # Add related parts info
                    related_parts = section.get('related_parts', [])
                    if related_parts:
                        parts_text = []
                        for part in related_parts:
                            if isinstance(part, dict):
                                parts_text.append(part.get('name', ''))
                        if parts_text:
                            text_parts.append("Related Parts: " + " | ".join(parts_text))
                    
                    full_text = "\n".join(filter(None, text_parts))
                    
                    if full_text.strip():
                        sections.append({
                            "text": full_text,
                            "appliance_type": appliance_type,
                            "symptom": symptom_title,
                            "issue_title": section.get('title', ''),
                            "source_file": json_file.name,
                            "section_id": section.get('id', ''),
                            "url": data.get('url', ''),
                            "instructions": instructions,
                            "related_parts": related_parts
                        })
            
            # Handle common symptoms (overview files like refrigerator_repair_guides.json)
            if "common_symptoms" in data:
                appliance_type_name = data.get("appliance_type", appliance_type)
                for symptom in data["common_symptoms"]:
                    # Create comprehensive text for embedding
                    text_parts = []
                    
                    symptom_title = symptom.get('title', '')
                    text_parts.append(f"Common Symptom: {symptom_title}")
                    text_parts.append(f"Description: {symptom.get('description', '')}")
                    
                    # Add percentage info
                    percentage = symptom.get('reported_by_percentage', 0)
                    if percentage:
                        text_parts.append(f"Reported by {percentage}% of customers")
                    
                    # Add appliance type context
                    text_parts.append(f"Appliance: {appliance_type_name}")
                    
                    full_text = "\n".join(filter(None, text_parts))
                    
                    if full_text.strip():
                        sections.append({
                            "text": full_text,
                            "appliance_type": appliance_type,
                            "symptom": symptom_title,
                            "issue_title": f"Common {symptom_title} Problem",
                            "source_file": json_file.name,
                            "section_id": symptom.get('url_slug', ''),
                            "url": symptom.get('url', ''),
                            "instructions": [symptom.get('description', '')],
                            "related_parts": [],
                            "percentage": percentage
                        })
            
            # Handle troubleshooting videos (overview files)
            if "troubleshooting_videos" in data:
                appliance_type_name = data.get("appliance_type", appliance_type)
                for video in data["troubleshooting_videos"]:
                    # Create comprehensive text for embedding
                    text_parts = []
                    
                    video_title = video.get('title', '')
                    text_parts.append(f"Troubleshooting Video: {video_title}")
                    text_parts.append(f"Video URL: {video.get('url', '')}")
                    text_parts.append(f"Video ID: {video.get('video_id', '')}")
                    text_parts.append(f"Appliance: {appliance_type_name}")
                    text_parts.append("Video troubleshooting guide available")
                    
                    full_text = "\n".join(filter(None, text_parts))
                    
                    if full_text.strip():
                        sections.append({
                            "text": full_text,
                            "appliance_type": appliance_type,
                            "symptom": "Video Guide",
                            "issue_title": video_title,
                            "source_file": json_file.name,
                            "section_id": video.get('video_id', ''),
                            "url": video.get('url', ''),
                            "instructions": [f"Watch troubleshooting video: {video.get('url', '')}"],
                            "related_parts": [],
                            "video_info": {
                                "title": video_title,
                                "url": video.get('url', ''),
                                "video_id": video.get('video_id', ''),
                                "thumbnail_url": video.get('thumbnail_url', '')
                            }
                        })
            
            return sections
            
        except Exception as e:
            logger.error(f"Error processing {json_file}: {e}")
            return []
    
    def build_index(self, rebuild: bool = False) -> Dict[str, Any]:
        """Build or load the RAG index"""
        logger.info(f"🔧 RAG build_index called: rebuild={rebuild}")
        logger.info(f"📁 Data directory: {self.data_dir.absolute()}")
        logger.info(f"📁 Index directory: {self.index_dir.absolute()}")
        logger.info(f"📄 Index file: {self.index_file}")
        logger.info(f"📄 Meta file: {self.meta_file}")
        
        if not RAG_AVAILABLE:
            error_msg = "RAG dependencies not installed - need faiss-cpu and sentence-transformers"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}
        
        logger.info(f"✅ RAG dependencies available")
        
        # Check if data directory exists
        if not self.data_dir.exists():
            error_msg = f"Data directory does not exist: {self.data_dir.absolute()}"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}
        
        # Load existing index if available and not rebuilding
        if not rebuild and self.index_file.exists() and self.meta_file.exists():
            logger.info("📂 Found existing index files, attempting to load...")
            try:
                self._load_existing_index()
                logger.info(f"✅ Successfully loaded existing index with {len(self._metadata)} documents")
                appliances = list(set(doc["appliance_type"] for doc in self._metadata))
                logger.info(f"🔧 Appliance types: {appliances}")
                return {
                    "status": "loaded_existing",
                    "documents": len(self._metadata),
                    "appliances": appliances
                }
            except Exception as e:
                logger.warning(f"⚠️ Failed to load existing index: {e}, rebuilding...")
        
        # Build new index
        logger.info("🏗️ Building RAG index from JSON files...")
        
        all_sections = []
        texts = []
        
        # Process all JSON files in data directory
        json_files = list(self.data_dir.rglob("*.json"))
        logger.info(f"📄 Found {len(json_files)} JSON files in data directory")
        
        for json_file in json_files:
            if json_file.name == "scraped_parts.json":
                logger.info(f"⏭️ Skipping parts file: {json_file.name}")
                continue  # Skip parts data
            
            logger.info(f"📖 Processing: {json_file.relative_to(self.data_dir)}")
            sections = self._extract_repair_sections(json_file)
            logger.info(f"   → Extracted {len(sections)} sections")
            all_sections.extend(sections)
            texts.extend([section["text"] for section in sections])
        
        if not texts:
            error_msg = f"No repair data found to index in {self.data_dir.absolute()}"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}
        
        logger.info(f"📊 Total sections to index: {len(texts)}")
        
        # Generate embeddings
        logger.info(f"🧠 Generating embeddings for {len(texts)} repair sections...")
        try:
            embeddings = self._embed_texts(texts)
            logger.info(f"✅ Generated embeddings shape: {embeddings.shape}")
        except Exception as e:
            error_msg = f"Failed to generate embeddings: {e}"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}
        
        # Create FAISS index
        logger.info("🔍 Creating FAISS index...")
        try:
            dimension = embeddings.shape[1]
            self._index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity for normalized vectors)
            self._index.add(embeddings)
            logger.info(f"✅ FAISS index created with dimension {dimension}")
        except Exception as e:
            error_msg = f"Failed to create FAISS index: {e}"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}
        
        # Save index and metadata
        logger.info("💾 Saving index and metadata...")
        try:
            faiss.write_index(self._index, str(self.index_file))
            logger.info(f"✅ Saved FAISS index to {self.index_file}")
            
            self._metadata = all_sections
            
            # Save metadata with data hash for cache invalidation
            metadata_with_hash = {
                "data_hash": self._calculate_data_hash(),
                "model_name": self.model_name,
                "documents_count": len(all_sections),
                "created_at": str(Path.cwd() / "timestamp"),  # Simple timestamp
                "sections": all_sections
            }
            
            with open(self.meta_file, 'w', encoding='utf-8') as f:
                json.dump(metadata_with_hash, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved metadata to {self.meta_file} with hash for caching")
        except Exception as e:
            error_msg = f"Failed to save index files: {e}"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}
        
        appliance_types = list(set(doc["appliance_type"] for doc in self._metadata))
        
        logger.info(f"🎉 RAG index built successfully!")
        logger.info(f"   📊 Documents: {len(self._metadata)}")
        logger.info(f"   🔧 Appliance types: {appliance_types}")
        
        return {
            "status": "built",
            "documents": len(self._metadata),
            "appliances": appliance_types
        }
    
    def _load_existing_index(self):
        """Load existing index from disk"""
        if not RAG_AVAILABLE:
            raise ImportError("RAG dependencies not installed")
        
        print(f"Loading existing index from {self.index_file}")
        self._index = faiss.read_index(str(self.index_file))
        
        with open(self.meta_file, 'r', encoding='utf-8') as f:
            metadata_obj = json.load(f)
        
        # Handle both old and new metadata formats
        if isinstance(metadata_obj, list):
            # Old format: just the sections list
            self._metadata = metadata_obj
            print(f"Loaded existing RAG index: {len(self._metadata)} documents (old format)")
        else:
            # New format: object with sections and metadata
            self._metadata = metadata_obj.get("sections", metadata_obj)
            docs_count = metadata_obj.get("documents_count", len(self._metadata))
            data_hash = metadata_obj.get("data_hash", "unknown")[:16]
            print(f"Loaded existing RAG index: {docs_count} documents (hash: {data_hash}...)")
    
    def search(self, query: str, appliance_type: str = None, top_k: int = 8) -> Dict[str, Any]:
        """Search for relevant repair information"""
        logger.info(f"🔍 RAG search called: query='{query}', appliance_type='{appliance_type}', top_k={top_k}")
        
        if not RAG_AVAILABLE:
            error_msg = "RAG dependencies not installed"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}
        
        # Ensure index is loaded
        if self._index is None:
            logger.info("📂 Index not loaded, attempting to load from disk...")
            try:
                self._load_existing_index()
                logger.info(f"✅ Index loaded successfully with {len(self._metadata)} documents")
            except Exception as e:
                error_msg = f"Index not available: {e}"
                logger.error(f"❌ {error_msg}")
                return {"error": error_msg}
        
        logger.info(f"🧠 Generating query embedding...")
        try:
            # Generate query embedding
            query_embedding = self._embed_query(query).reshape(1, -1)
            logger.info(f"✅ Query embedding generated: shape {query_embedding.shape}")
        except Exception as e:
            error_msg = f"Failed to generate query embedding: {e}"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}
        
        # Search with higher k to allow filtering
        search_k = max(top_k * 3, 20)
        logger.info(f"🔍 Searching FAISS index with k={search_k}...")
        
        try:
            scores, indices = self._index.search(query_embedding, search_k)
            logger.info(f"✅ FAISS search completed, found {len(indices[0])} results")
        except Exception as e:
            error_msg = f"FAISS search failed: {e}"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}
        
        results = []
        filtered_count = 0
        
        for idx, score in zip(indices[0], scores[0]):
            if idx == -1:  # FAISS returns -1 for invalid indices
                continue
            
            doc = self._metadata[idx]
            
            # Filter by appliance type if specified
            if appliance_type and doc["appliance_type"].lower() != appliance_type.lower():
                filtered_count += 1
                continue
            
            results.append({
                "score": float(score),
                "appliance_type": doc["appliance_type"],
                "symptom": doc["symptom"],
                "issue_title": doc["issue_title"],
                "text": doc["text"],
                "instructions": doc["instructions"],
                "related_parts": doc["related_parts"],
                "source_file": doc["source_file"],
                "url": doc["url"]
            })
            
            if len(results) >= top_k:
                break
        
        logger.info(f"🎯 Search results: {len(results)} returned, {filtered_count} filtered out")
        if results:
            logger.info(f"   Top result: {results[0]['symptom']} - {results[0]['issue_title']} (score: {results[0]['score']:.3f})")
        
        return {
            "query": query,
            "appliance_type": appliance_type,
            "results": results,
            "total_found": len(results)
        }

# Global RAG system instance
_rag_system = None

def get_rag_system() -> RepairRAGSystem:
    """Get or create the global RAG system instance"""
    global _rag_system
    if _rag_system is None:
        print(f"Creating new RAG system instance...")
        print(f"Current working directory: {Path.cwd()}")
        _rag_system = RepairRAGSystem()
        
        # Auto-initialize the RAG system when first accessed
        print("Auto-initializing RAG system...")
        try:
            # Check if we need to rebuild based on data freshness
            rebuild_needed = _rag_system._should_rebuild_index()
            print(f"Rebuild needed: {rebuild_needed}")
            
            result = _rag_system.build_index(rebuild=rebuild_needed)
            if "error" in result:
                print(f"RAG auto-initialization failed: {result['error']}")
            else:
                print(f"RAG auto-initialization successful: {result.get('documents', 0)} documents")
                if not rebuild_needed:
                    print("Used cached index - startup was faster!")
        except Exception as e:
            print(f"RAG auto-initialization error: {e}")
            
    return _rag_system

def initialize_rag_system(rebuild: bool = False) -> Dict[str, Any]:
    """Initialize the RAG system and build index if needed"""
    logger.info(f"🚀 initialize_rag_system called: rebuild={rebuild}")
    try:
        rag = get_rag_system()
        result = rag.build_index(rebuild=rebuild)
        logger.info(f"✅ RAG system initialization result: {result}")
        return result
    except Exception as e:
        error_msg = f"Failed to initialize RAG system: {e}"
        logger.error(f"❌ {error_msg}")
        import traceback
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        return {"error": error_msg}

def search_repair_guides(query: str, appliance_type: str = None, top_k: int = 8) -> Dict[str, Any]:
    """Search for repair guides using RAG"""
    logger.info(f"🔍 search_repair_guides called: query='{query}', appliance_type='{appliance_type}'")
    try:
        rag = get_rag_system()
        result = rag.search(query, appliance_type, top_k)
        logger.info(f"✅ Search completed: found {result.get('total_found', 0)} results")
        return result
    except Exception as e:
        error_msg = f"Failed to search repair guides: {e}"
        logger.error(f"❌ {error_msg}")
        import traceback
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        return {"error": error_msg}
