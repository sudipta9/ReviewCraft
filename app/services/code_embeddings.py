"""
Code Embeddings Service

This module provides semantic code analysis using sentence transformers
for code similarity, duplicate detection, and semantic search.

Features:
- Code embedding generation using sentence-transformers
- Semantic similarity analysis
- Code duplicate detection
- Fast local inference without external API calls
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
from structlog import get_logger

logger = get_logger(__name__)


class CodeEmbeddingsService:
    """
    Service for generating and analyzing code embeddings.

    Uses sentence-transformers for semantic understanding of code,
    enabling similarity analysis and duplicate detection.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize the embeddings service.

        Args:
            model_name: Name of the sentence-transformers model to use
        """
        self.model_name = model_name
        self._model = None
        self._initialize_model()

        logger.info(
            "Code Embeddings Service initialized",
            model=model_name,
            embedding_dim=self.get_embedding_dimension(),
        )

    def _initialize_model(self):
        """Initialize the sentence transformer model."""
        try:
            logger.info("Loading sentence transformer model", model=self.model_name)
            self._model = SentenceTransformer(self.model_name)
            logger.info("Model loaded successfully", model=self.model_name)
        except Exception as e:
            logger.error(
                "Failed to load sentence transformer model",
                model=self.model_name,
                error=str(e),
            )
            self._model = None

    def get_embedding_dimension(self) -> int | None:
        """Get the dimension of embeddings produced by the model."""
        if self._model is None:
            return 384  # Default for all-MiniLM-L6-v2
        return self._model.get_sentence_embedding_dimension()

    def encode_code(self, code_content: str, normalize: bool = True) -> np.ndarray:
        """
        Generate embeddings for code content.

        Args:
            code_content: The code to encode
            normalize: Whether to normalize the embedding vector

        Returns:
            numpy array of embeddings
        """
        if self._model is None:
            logger.warning("Model not available, returning zero vector")
            return np.zeros(384)

        try:
            # Preprocess code for better embeddings
            processed_code = self._preprocess_code(code_content)

            # Generate embeddings
            embedding = self._model.encode(
                processed_code, normalize_embeddings=normalize, show_progress_bar=False
            )

            # Convert to numpy array
            return np.array(embedding)

        except Exception as e:
            logger.error("Failed to encode code", error=str(e))
            embedding_dim = self.get_embedding_dimension()
            if embedding_dim is None:
                embedding_dim = 384  # Default fallback
            return np.zeros(embedding_dim)

    def encode_code_batch(
        self, code_contents: List[str], normalize: bool = True
    ) -> np.ndarray:
        """
        Generate embeddings for multiple code pieces.

        Args:
            code_contents: List of code strings to encode
            normalize: Whether to normalize the embedding vectors

        Returns:
            numpy array of embeddings (n_samples, embedding_dim)
        """
        if self._model is None:
            logger.warning("Model not available, returning zero vectors")
            return np.zeros((len(code_contents), 384))

        try:
            # Preprocess all code pieces
            processed_codes = [self._preprocess_code(code) for code in code_contents]

            # Generate embeddings for batch
            embeddings = self._model.encode(
                processed_codes,
                normalize_embeddings=normalize,
                show_progress_bar=False,
                batch_size=32,
            )

            # Convert to numpy array if needed
            return np.array(embeddings)

        except Exception as e:
            logger.error("Failed to encode code batch", error=str(e))
            embedding_dim = self.get_embedding_dimension()
            if embedding_dim is None:
                embedding_dim = 384  # Default fallback
            return np.zeros((len(code_contents), embedding_dim))

    def calculate_similarity(
        self, code1: str, code2: str, use_embeddings: bool = True
    ) -> float:
        """
        Calculate semantic similarity between two code pieces.

        Args:
            code1: First code piece
            code2: Second code piece
            use_embeddings: Whether to use embeddings (True) or simple comparison

        Returns:
            Similarity score between 0 and 1
        """
        if not use_embeddings or self._model is None:
            return self._simple_similarity(code1, code2)

        try:
            # Generate embeddings
            embedding1 = self.encode_code(code1)
            embedding2 = self.encode_code(code2)

            # Calculate cosine similarity
            similarity = np.dot(embedding1, embedding2) / (
                np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
            )

            # Ensure similarity is in [0, 1] range
            return max(0.0, min(1.0, float(similarity)))

        except Exception as e:
            logger.error("Failed to calculate similarity", error=str(e))
            return self._simple_similarity(code1, code2)

    def find_similar_code(
        self,
        target_code: str,
        code_database: List[Dict[str, Any]],
        threshold: float = 0.7,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find similar code pieces from a database.

        Args:
            target_code: Code to find similarities for
            code_database: List of code entries with 'content' and metadata
            threshold: Minimum similarity threshold
            top_k: Maximum number of results to return

        Returns:
            List of similar code entries with similarity scores
        """
        if self._model is None or not code_database:
            return []

        try:
            # Generate embedding for target code
            target_embedding = self.encode_code(target_code)

            # Generate embeddings for database
            db_contents = [entry.get("content", "") for entry in code_database]
            db_embeddings = self.encode_code_batch(db_contents)

            # Calculate similarities
            similarities = np.dot(db_embeddings, target_embedding)

            # Find matches above threshold
            results = []
            for i, similarity in enumerate(similarities):
                if similarity >= threshold:
                    result = code_database[i].copy()
                    result["similarity_score"] = float(similarity)
                    results.append(result)

            # Sort by similarity and return top_k
            results.sort(key=lambda x: x["similarity_score"], reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error("Failed to find similar code", error=str(e))
            return []

    def detect_code_duplicates(
        self, code_pieces: List[Dict[str, Any]], threshold: float = 0.8
    ) -> List[Tuple[int, int, float]]:
        """
        Detect potential code duplicates in a collection.

        Args:
            code_pieces: List of code entries with 'content' field
            threshold: Similarity threshold for considering duplicates

        Returns:
            List of tuples (index1, index2, similarity_score) for duplicates
        """
        if self._model is None or len(code_pieces) < 2:
            return []

        try:
            # Generate embeddings for all code pieces
            contents = [piece.get("content", "") for piece in code_pieces]
            embeddings = self.encode_code_batch(contents)

            # Find pairwise similarities
            duplicates = []
            n = len(embeddings)

            for i in range(n):
                for j in range(i + 1, n):
                    similarity = np.dot(embeddings[i], embeddings[j])
                    if similarity >= threshold:
                        duplicates.append((i, j, float(similarity)))

            # Sort by similarity score
            duplicates.sort(key=lambda x: x[2], reverse=True)

            logger.info(
                "Duplicate detection completed",
                total_pieces=n,
                duplicates_found=len(duplicates),
                threshold=threshold,
            )

            return duplicates

        except Exception as e:
            logger.error("Failed to detect duplicates", error=str(e))
            return []

    def analyze_code_similarity_metrics(
        self, file_content: str, function_extractor=None
    ) -> Dict[str, Any]:
        """
        Analyze various similarity metrics for code content.

        Args:
            file_content: Code content to analyze
            function_extractor: Optional function to extract code blocks

        Returns:
            Dictionary with similarity analysis results
        """
        try:
            # Extract functions/methods if extractor provided
            if function_extractor:
                code_blocks = function_extractor(file_content)
            else:
                # Simple line-based splitting as fallback
                code_blocks = self._extract_code_blocks(file_content)

            if len(code_blocks) < 2:
                return {
                    "total_blocks": len(code_blocks),
                    "duplicates_found": 0,
                    "max_similarity": 0.0,
                    "avg_similarity": 0.0,
                    "duplication_score": 0.0,
                }

            # Detect duplicates
            block_data = [{"content": block} for block in code_blocks]
            duplicates = self.detect_code_duplicates(block_data, threshold=0.7)

            # Calculate metrics
            if duplicates:
                similarities = [dup[2] for dup in duplicates]
                max_similarity = max(similarities)
                avg_similarity = sum(similarities) / len(similarities)
            else:
                max_similarity = 0.0
                avg_similarity = 0.0

            # Calculate overall duplication score
            duplication_score = len(duplicates) / max(
                1, len(code_blocks) * (len(code_blocks) - 1) / 2
            )

            return {
                "total_blocks": len(code_blocks),
                "duplicates_found": len(duplicates),
                "max_similarity": max_similarity,
                "avg_similarity": avg_similarity,
                "duplication_score": min(1.0, duplication_score),
                "duplicate_pairs": duplicates[:5],  # Top 5 duplicates
            }

        except Exception as e:
            logger.error("Failed to analyze similarity metrics", error=str(e))
            return {
                "total_blocks": 0,
                "duplicates_found": 0,
                "max_similarity": 0.0,
                "avg_similarity": 0.0,
                "duplication_score": 0.0,
            }

    def _preprocess_code(self, code_content: str) -> str:
        """
        Preprocess code for better embedding generation.

        Args:
            code_content: Raw code content

        Returns:
            Preprocessed code string
        """
        # Remove excessive whitespace and empty lines
        lines = [line.strip() for line in code_content.split("\n") if line.strip()]

        # Join with single spaces to create a cleaner representation
        processed = " ".join(lines)

        # Limit length to avoid token limits
        max_length = 512  # Reasonable limit for most models
        if len(processed) > max_length:
            processed = processed[:max_length]

        return processed

    def _extract_code_blocks(self, file_content: str) -> List[str]:
        """
        Extract code blocks from file content (simple implementation).

        Args:
            file_content: File content to process

        Returns:
            List of code blocks
        """
        lines = file_content.split("\n")
        blocks = []
        current_block = []

        for line in lines:
            stripped = line.strip()

            # Simple heuristic: start new block on function/class definitions
            if (
                stripped.startswith("def ")
                or stripped.startswith("class ")
                or stripped.startswith("function ")
                or stripped.startswith("const ")
                or stripped.startswith("let ")
                or stripped.startswith("var ")
            ):

                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []

            if stripped:  # Only add non-empty lines
                current_block.append(line)

        # Add the last block
        if current_block:
            blocks.append("\n".join(current_block))

        return blocks

    def _simple_similarity(self, code1: str, code2: str) -> float:
        """
        Simple similarity calculation as fallback.

        Args:
            code1: First code piece
            code2: Second code piece

        Returns:
            Basic similarity score
        """
        # Simple Jaccard similarity on words
        words1 = set(code1.lower().split())
        words2 = set(code2.lower().split())

        if not words1 and not words2:
            return 1.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0
