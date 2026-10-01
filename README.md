# InvoiceGuard

## What InvoiceGuard is
InvoiceGuard is a portfolio-grade business software project designed for Indian MSMEs, especially small/medium manufacturing and distribution businesses.

## The Business Problem
Finance and procurement teams often spend significant manual effort checking vendor invoices against Purchase Orders (POs) and identifying discrepancies. InvoiceGuard aims to streamline this process through a deterministic verification approach: "AI handles ambiguity. Code handles certainty. Humans handle exceptions."

## Current Development Phase
**Phase M1.1 - Project Foundation**
This phase focuses solely on creating a clean backend foundation that can run locally. It does not include database models, authentication, payment systems, ERP integrations, OCR, or complex business logic.

## Current Technology Stack
- **Backend**: Python, FastAPI, Uvicorn, Pydantic, python-dotenv / pydantic-settings

*(Note: PostgreSQL, SQLAlchemy, Alembic, Next.js, and TypeScript are planned for future phases.)*

## How to run the backend locally
1. Navigate to the `backend` directory.
2. Activate the virtual environment:
   ```bash
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the server:
   ```bash
   uvicorn app.main:app --reload
   ```

## API Endpoints Currently Available
- `GET /` : Returns a welcome message.
- `GET /health` : Returns the health status of the application.
- `GET /docs` : Interactive Swagger API documentation.
- `GET /redoc` : ReDoc API documentation.

## Future Planned Architecture
See [docs/architecture.md](docs/architecture.md) for details on the future document flow and system architecture.
