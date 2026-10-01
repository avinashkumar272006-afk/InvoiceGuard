# Architecture

## Current Planned High-Level Architecture

Next.js Frontend
↓
FastAPI Backend
↓
Business Services
↓
SQLAlchemy (ORM)
↓
PostgreSQL

## Database Foundation

*   **PostgreSQL**: Chosen as the primary relational database for its robust JSON support, concurrency, and reliability for transactional data.
*   **SQLAlchemy**: Provides a powerful ORM and query builder for Python, allowing safe and structured interaction with the database.
*   **Alembic**: Used for database schema migrations, ensuring that structure changes can be versioned and deployed predictably.
*   **Credentials**: Database credentials and connection strings are strictly managed via environment variables (e.g., `.env`) to prevent exposing sensitive information in source code.

## Future Document Flow

Invoice
↓
Document Extraction
↓
Structured Invoice Data
↓
PO Matching
↓
Deterministic Verification
↓
Exception Detection
↓
Human Review
↓
Audit Trail

*Important Note: OCR and AI are future components and are NOT implemented in Phase M1.1.*
