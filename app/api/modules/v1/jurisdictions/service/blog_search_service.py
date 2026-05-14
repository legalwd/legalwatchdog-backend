import logging
from collections import Counter
from typing import Any, List, Optional, Sequence, Union, cast
from uuid import UUID

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import (
    BlogPostToken,
    JurisdictionBlogPost,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.schemas.blog_schema import BlogPostResponse
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.utils.project_utils import calculate_pagination

logger = logging.getLogger(__name__)
lemmatizer = WordNetLemmatizer()


class StopwordsManager:
    _stop_words: set[str] | None = None

    @classmethod
    def get(cls) -> set[str]:
        if cls._stop_words is None:
            import nltk

            from app.api.core.config import NLTK_DATA_PATH

            nltk.data.path.append(str(NLTK_DATA_PATH))
            try:
                nltk.download("stopwords", download_dir=str(NLTK_DATA_PATH), quiet=True)
            except Exception:
                pass
            cls._stop_words = set(stopwords.words("english"))
        return cls._stop_words


class BlogPostCrud:
    async def get_all_blog_post(
        self, db: AsyncSession, organization_id: Optional[UUID] = None
    ) -> Sequence[JurisdictionBlogPost]:
        """
        Fetch all published blog posts, optionally filtered by organization.

        Args:
            db (AsyncSession): Database session for async queries.
            organization_id (Optional[str]): UUID of the organization \
                to filter posts. Defaults to None.

        Returns:
            Sequence[JurisdictionBlogPost]: List of published blog posts.

        Raises:
            SQLAlchemyError: If the query fails due to database issues.
        """
        try:
            stmt = select(JurisdictionBlogPost).where(
                cast(Any, JurisdictionBlogPost.is_published).is_(True)
            )

            if organization_id:
                stmt = (
                    stmt.join(Jurisdiction)
                    .join(Project)
                    .where(cast(Any, Project.org_id) == organization_id)
                )

            result = await db.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.exception(f"Error fetching blog posts from DB: {str(e)}")
            raise

    async def get_tokens_for_post(self, db: AsyncSession, post_id: UUID) -> Sequence[BlogPostToken]:
        """
        Retrieve all tokens for a given blog post.

        Args:
            db: AsyncSession instance.
            post_id: UUID of the blog post.

        Returns:
            List of BlogPostToken objects for the post.
        """
        stmt = select(BlogPostToken).where(cast(Any, BlogPostToken.post_id) == post_id)
        result = await db.execute(stmt)
        return result.scalars().all()

    def update_post_tokens(self, db: Session, post_id: UUID, fields: dict):
        """
        Tokenize and store blog post fields for search and ranking.

        All tokens from 'content' are stored (duplicates preserved) to allow
        frequency-based relevancy ranking. Other fields ('title', 'keywords',
        'meta_description') store only unique tokens to save space.

        Args:
            db (Session): SQLAlchemy session for DB operations.
            post_id (UUID): ID of the blog post.
            fields (dict): Mapping of field names to string or list of strings.

        Example:
                fields = {"title": "Async Python", "content": "Async is powerful"}
                crud.update_post_tokens(db, post_id, fields)
        """
        db.execute(delete(BlogPostToken).where(cast(Any, BlogPostToken.post_id) == post_id))

        tokens_to_insert = []
        STOP_WORDS = StopwordsManager.get()

        for field_name, value in fields.items():
            values = value if isinstance(value, list) else [value]

            for v in values:
                words = [lemmatizer.lemmatize(w.lower()) for w in word_tokenize(v) if w.isalnum()]
                words = [w for w in words if w not in STOP_WORDS]

                if field_name == "content":
                    for token in words:
                        tokens_to_insert.append(
                            BlogPostToken(post_id=post_id, word_token=token, field=field_name)
                        )
                else:
                    for token in set(words):
                        tokens_to_insert.append(
                            BlogPostToken(post_id=post_id, word_token=token, field=field_name)
                        )

        if tokens_to_insert:
            db.add_all(tokens_to_insert)
            db.commit()


crud = BlogPostCrud()


class BlogSearchService:
    field_priority = {
        "title": 1,
        "keywords": 2,
        "content": 3,
        "meta_description": 4,
    }

    def word_tokenization(self, sentence):
        return word_tokenize(sentence)

    def remove_stop_words(self, tokens):
        STOP_WORDS = StopwordsManager.get()
        return [word for word in tokens if word.lower() not in STOP_WORDS]

    def lemmatization(self, tokens):
        return [lemmatizer.lemmatize(token.lower()) for token in tokens if token.isalnum()]

    def word_frequency(self, words, data=None):
        """Count frequencies in `words` and optionally filter keys by `data`.

        Args:
            words: iterable of words to count (typically tokens from content)
            data: optional iterable of filter terms; when provided only counts
                  for those terms will be returned.
        Returns:
            Counter of word -> frequency (possibly filtered).
        """
        count = Counter(words)
        if data:
            data_set = set(data)
            count = Counter({w: freq for w, freq in count.items() if w in data_set})
        return count

    def deduplication(self, data):
        return list(set(data))

    def preprocess_query(self, query_terms: Union[List[str], str]) -> List[str]:
        if isinstance(query_terms, str):
            query_terms = self.word_tokenization(query_terms)
        query_terms = self.remove_stop_words(query_terms)
        query_terms = self.lemmatization(query_terms)
        query_terms = self.deduplication(query_terms)
        return query_terms

    def assign_rank(self, post: JurisdictionBlogPost, matched_field: str) -> int:
        return self.field_priority.get(matched_field, 999)

    async def rank_n_sort_posts(
        self,
        db: AsyncSession,
        posts: List[JurisdictionBlogPost],
        query_terms: Union[List[str], str],
    ) -> List[JurisdictionBlogPost]:
        """
        Rank and sort blog posts based on relevance to the given query terms.

        Each post is scored according to:
            - Matching query terms in title, keywords, content, or meta_description.
            - Field priority (title > keywords > content > meta_description).
            - Frequency of matching terms in the content (content duplicates are kept for ranking).
            - Recency of the post (updated_at timestamp).

        Args:
            db (AsyncSession): Async SQLAlchemy session for querying BlogPostToken table.
            posts (List[JurisdictionBlogPost]): List of blog posts to rank.
            query_terms (Union[List[str], str]): Search terms as a string or list of strings.

        Returns:
            List[JurisdictionBlogPost]: Posts sorted by relevance, frequency, and recency.
        """
        query_terms = self.preprocess_query(query_terms)
        ranked_list = []

        for post in posts:
            matched_field = None
            total_frequency = 0

            tokens = await crud.get_tokens_for_post(db=db, post_id=post.id)

            field_tokens_map = {}
            for t in tokens:
                field_tokens_map.setdefault(t.field, []).append(t.word_token)

            title_tokens = field_tokens_map.get("title", [])
            content_tokens = field_tokens_map.get("content", [])
            meta_tokens = field_tokens_map.get("meta_description", [])
            keywords_tokens = field_tokens_map.get("keywords", [])

            if any(term in title_tokens for term in query_terms):
                matched_field = "title"
            elif any(term in keywords_tokens for term in query_terms):
                matched_field = "keywords"
            elif any(term in content_tokens for term in query_terms):
                matched_field = "content"
                freq_counter = self.word_frequency(content_tokens, query_terms)
                total_frequency = sum(freq_counter.values())
            elif any(term in meta_tokens for term in query_terms):
                matched_field = "meta_description"
            else:
                matched_field = "unknown"

            rank = self.assign_rank(post, matched_field)
            ranked_list.append(
                {
                    "post": post,
                    "rank": rank,
                    "updated_at": post.updated_at,
                    "total_frequency": total_frequency,
                }
            )

        ranked_list = sorted(
            ranked_list,
            key=lambda x: (x["rank"], -x.get("total_frequency", 0), -x["updated_at"].timestamp()),
        )

        return [x["post"] for x in ranked_list]

    async def get_all_blog_posts_service(
        self,
        db: AsyncSession,
        organization_id: UUID,
        query_terms: Optional[Union[List[str], str]] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """
        Retrieve, rank, and paginate all published blog posts based on query terms.

        Args:
            db (AsyncSession): Database session for async queries.
            query_terms (Union[List[str], str]): Search terms to match against blog post tokens.
            page (int, optional): Page number for pagination. Defaults to 1.
            limit (int, optional): Number of posts per page. Defaults to 20.

        Returns:
            dict: Paginated dictionary containing:
                - 'total': Total number of ranked posts.
                - 'page': Current page number.
                - 'limit': Posts per page.
                - 'items': List of `JurisdictionBlogPost` objects for the current page.

        Raises:
            SQLAlchemyError: If any database operation fails \
                (e.g., connection issues, query errors).
            ValueError: If `page` or `limit` are invalid (non-positive integers).
            TypeError: If `query_terms` is neither a string nor a list of strings.
        """
        try:
            if not isinstance(page, int) or page < 1 or not isinstance(limit, int) or limit < 1:
                raise ValueError("Invalid pagination parameters")

            if not isinstance(query_terms, (list, str)):
                raise TypeError("query_terms must be a string or list of strings")

            blog_posts = list(await crud.get_all_blog_post(db, organization_id=organization_id))
            if query_terms:
                blog_posts = await self.rank_n_sort_posts(
                    db=db, posts=blog_posts, query_terms=query_terms
                )

            posts_data = [
                BlogPostResponse.model_validate(post).model_dump(mode="json") for post in blog_posts
            ]

            total = len(posts_data)

            pagination = calculate_pagination(total=total, page=page, limit=limit)

            start = (page - 1) * limit
            end = start + limit

            return {
                "status_code": 200,
                "message": "Blog posts retrieved successfully",
                "data": {"items": posts_data[start:end], "pagination": pagination},
            }
        except TypeError as te:
            logger.exception(f"Invalid type passed to get_all_blog_posts_service: {str(te)}")
            raise ProcessingError(message="Invalid query terms provided")
        except Exception as e:
            logger.exception(f"Error retrieving blog posts: {str(e)}")
            raise ProcessingError(message="Error fetching blog posts")
