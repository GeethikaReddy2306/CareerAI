# AI-Powered Career Intelligence, Preparation & Upskilling Platform

Comprehensive backend for an **AI-Powered Career Intelligence, Preparation & Upskilling Platform** built using **FastAPI**, **SQLAlchemy 2.x**, **PostgreSQL**, **Alembic**, **PyMuPDF**, and **OpenAI**.

---

## Tech Stack

- **Runtime**: Python 3.11+
- **Framework**: FastAPI
- **Server**: Uvicorn
- **Database & ORM**: PostgreSQL / SQLite (for testing & local dev), SQLAlchemy 2.x
- **Data Validation & Settings**: Pydantic v2 & Pydantic Settings
- **Migrations**: Alembic
- **Authentication**: JWT (JSON Web Tokens) with Bearer token header
- **Password Hashing**: `pwdlib` with `bcrypt`
- **PDF Text Extraction**: PyMuPDF (`pymupdf`)
- **AI Engine**: Reusable OpenAI Service (`gpt-4o-mini` with JSON output) + Deterministic Heuristic Fallbacks
- **Testing**: Pytest & HTTPX (37 automated tests)

---

## Implemented Platform Capabilities

1. **User Authentication**: Secure registration, email uniqueness, Bcrypt password hashing, Bearer JWT token issuance, protected `/me` profile.
2. **Resume Management & PDF Parsing**: Multi-page PDF text extraction via PyMuPDF, file-type and size validation (max 5 MB), safe UUID filenames, resume deletion with disk cleanup.
3. **Structured AI Resume Analysis**: AI-powered career profiling extracting Summary, Skills, Education, Projects, Certifications, Work Experience, Strengths, Weaknesses, Experience Level, and Suggested Roles.
4. **Transparent ATS Resume Scoring**: Deterministic 6-factor ATS scoring (0-100) with category breakdown, detected & missing sections, and concrete actionable suggestions.
5. **Resume + Job Description Analysis**: Meaningful candidate vs. JD comparison determining matched skills, partial skills, missing skills, important keywords, tailored interview topics, recommendations, and a composite match score (0-100).
6. **Skill Gap Engine & Normalization**: Deterministic skill normalization (e.g. `ReactJS` -> `React`, `NodeJS` -> `Node.js`, `postgres` -> `PostgreSQL`), categorizing skills into `Strong`, `Intermediate`, `Weak`, and `Missing`, with actionable priority levels (`High`, `Medium`, `Low`).
7. **Career Readiness Score**: Measurable 5-factor scoring model combining Skill Match (35%), Resume Quality (20%), Project Experience (15%), Interview Readiness (15%), and Experience Relevance (15%).
8. **Personalized Career Roadmap**: Gap-aware multi-phase chronological milestones. Never recommends basics the candidate already knows; focuses on missing/weak skills, practical projects, and estimated duration.
9. **Personalized Interview Questions**: Generates tailored interview questions across 7 core dimensions: `Technical`, `Resume Based`, `Project Based`, `Role Specific`, `Skill Gap Based`, `Behavioral`, and `HR`, with difficulty levels (`Easy`, `Medium`, `Hard`).

---

## Project Architecture & Folder Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application, OpenAPI tags, global error handling
│   ├── core/
│   │   ├── config.py               # Pydantic Settings & environment variable configuration
│   │   ├── database.py             # SQLAlchemy 2.x engine, SessionLocal, Declarative Base, get_db
│   │   └── security.py             # Bcrypt password hashing & JWT encode/decode
│   ├── models/
│   │   ├── __init__.py             # Exports all SQLAlchemy models
│   │   ├── user.py                 # User table (users)
│   │   ├── resume.py               # Resume table (resumes)
│   │   ├── resume_analysis.py      # ResumeAnalysis table (resume_analyses)
│   │   ├── job_analysis.py         # JobAnalysis table (job_analyses)
│   │   ├── career_roadmap.py       # CareerRoadmap table (roadmaps)
│   │   └── interview_question.py   # InterviewQuestion table (interview_questions)
│   ├── schemas/
│   │   ├── __init__.py             # Exports all Pydantic schemas
│   │   ├── common.py               # APIResponse[T], ErrorResponse
│   │   ├── auth.py                 # UserRegisterRequest, UserLoginRequest, TokenResponse
│   │   ├── user.py                 # UserResponse, UserMeResponse
│   │   ├── resume.py               # ResumeResponse, ResumeDetailResponse, ResumeUploadResponse
│   │   ├── resume_analysis.py      # AIResumeAnalysisResult, ATSScoreResponse, ResumeAnalysisDetailResponse
│   │   ├── job_analysis.py         # JobAnalysisRequest, JobAnalysisResponse
│   │   ├── skill_gap.py            # SkillGapRequest, PrioritizedSkillItem, SkillGapResponse
│   │   ├── career_readiness.py     # CareerReadinessBreakdown, CareerReadinessResponse
│   │   ├── career_roadmap.py       # RoadmapPhase, RoadmapResponse, RoadmapCreateRequest
│   │   └── interview.py            # InterviewQuestionItem, InterviewQuestionsRequest, InterviewQuestionsResponse
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py                 # /api/auth/register, /api/auth/login, /api/auth/me
│   │   ├── resume.py               # /api/resumes/upload, list, get, delete
│   │   ├── analysis.py             # /api/resumes/{id}/analyze, /api/resumes/{id}/ats-score, /api/resumes/{id}/analysis
│   │   ├── job_analysis.py         # /api/job-analysis
│   │   ├── skill_gap.py            # /api/skill-gap
│   │   ├── career_readiness.py     # /api/career-readiness
│   │   ├── career_roadmap.py       # /api/career/roadmap (POST & GET)
│   │   └── interview.py            # /api/interview/questions (POST & GET)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai_service.py           # Centralized reusable OpenAI client with heuristic fallbacks
│   │   ├── auth_service.py         # Registration & authentication business logic
│   │   ├── resume_parser.py        # PyMuPDF PDF text extraction
│   │   ├── ai_resume_analyzer.py   # Structured resume profile extractor
│   │   ├── ats_service.py          # Deterministic 6-factor ATS scoring engine (0-100)
│   │   ├── skill_gap_service.py    # Skill normalization & gap categorization
│   │   ├── job_analysis_service.py # Resume vs JD matching & score calculation
│   │   ├── career_readiness_service.py # Multi-factor 0-100 readiness scoring
│   │   ├── roadmap_service.py      # Personalized career roadmap generator
│   │   └── interview_service.py    # 7-category personalized interview question generator
│   └── dependencies/
│       ├── __init__.py
│       └── auth.py                 # get_current_user JWT dependency
├── migrations/
│   ├── env.py                      # Alembic runtime environment
│   ├── script.py.mako              # Revision template
│   └── versions/
│       ├── 001_initial_schema.py   # Migration for users, resumes, resume_analyses
│       └── 002_phase2_features.py  # Migration for job_analyses, roadmaps, interview_questions
├── uploads/
│   └── resumes/                    # Secure local storage for uploaded PDF resumes (.gitkeep)
├── tests/
│   ├── conftest.py                 # In-memory DB, TestClient, test user & PDF generator fixtures
│   ├── test_auth.py                # Auth endpoint test suite
│   ├── test_resumes.py             # Resume upload, parsing, isolation tests
│   ├── test_ats_analysis.py        # ATS scoring engine and AI analysis caching tests
│   ├── test_e2e_flow.py            # Phase 1 acceptance flow test
│   ├── test_job_analysis.py        # Job Analysis endpoint tests
│   ├── test_skill_gap.py           # Skill Gap and normalization tests
│   ├── test_career_readiness.py    # Career Readiness score tests
│   ├── test_roadmap.py             # Career Roadmap tests
│   ├── test_interview.py           # Interview Question Generation tests
│   └── test_phase2_e2e.py          # Complete platform lifecycle integration test
├── .env.example                    # Environment template
├── .gitignore                      # Git ignore file
├── pytest.ini                      # Pytest configuration
├── requirements.txt                # Pinned dependencies
├── alembic.ini                     # Alembic configuration
└── README.md                       # Comprehensive setup and API documentation
```

---

## Database Tables

1. **`users`**: User identity and hashed passwords.
2. **`resumes`**: Stored PDF resumes, file metadata, and extracted text.
3. **`resume_analyses`**: Structured candidate profile (JSON) and ATS scores.
4. **`job_analyses`**: Resume vs JD comparison, match scores, matched/partial/missing skills, and recommendations.
5. **`roadmaps`**: Phased, personalized upskilling roadmaps tailored to candidate skill gaps.
6. **`interview_questions`**: Personalized questions categorized into Technical, Resume Based, Project Based, Role Specific, Skill Gap Based, Behavioral, and HR.

---

## Environment Variables

Configure these inside a `.env` file (copied from `.env.example`):

```env
# Database Configuration (PostgreSQL preferred)
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/career_db

# Security & Authentication
SECRET_KEY=replace-with-a-secure-random-secret-key-at-least-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# OpenAI API
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini

# File Storage
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_BYTES=5242880

# Environment
ENVIRONMENT=development
```

---

## Installation & Setup

### 1. Activate Environment & Install Dependencies
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Run Database Migrations
```bash
alembic upgrade head
```

### 3. Start Application Server
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Interactive Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Alternative ReDoc UI: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## API Endpoints Summary

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/auth/register` | Register new user account | No |
| `POST` | `/api/auth/login` | Login and receive Bearer JWT token | No |
| `GET` | `/api/auth/me` | Get current user profile | **Yes** |
| `POST` | `/api/resumes/upload` | Upload PDF resume, parse text | **Yes** |
| `GET` | `/api/resumes` | List resumes for current user | **Yes** |
| `GET` | `/api/resumes/{id}` | Get single resume details | **Yes** |
| `DELETE` | `/api/resumes/{id}` | Delete resume and file from disk | **Yes** |
| `POST` | `/api/resumes/{id}/analyze` | Extract structured AI career profile | **Yes** |
| `POST` | `/api/resumes/{id}/ats-score` | Compute deterministic ATS score (0-100) | **Yes** |
| `GET` | `/api/resumes/{id}/analysis` | Get saved profile and ATS feedback | **Yes** |
| `POST` | `/api/job-analysis` | Compare resume vs job description | **Yes** |
| `POST` | `/api/skill-gap` | Analyze skill gaps with normalization | **Yes** |
| `GET` | `/api/career-readiness` | Compute 5-factor career readiness score | **Yes** |
| `POST` | `/api/career/roadmap` | Generate gap-focused career roadmap | **Yes** |
| `GET` | `/api/career/roadmap` | Retrieve saved career roadmap | **Yes** |
| `POST` | `/api/interview/questions` | Generate 7-category interview questions | **Yes** |
| `GET` | `/api/interview/questions` | Retrieve saved interview questions | **Yes** |

---

## Running Automated Tests

Run the full pytest suite:
```bash
pytest -v
```
All **37 test cases** pass cleanly, validating user authentication, PDF extraction, cross-user ownership isolation, ATS scoring, Job Description matching, Skill Gap analysis, Career Readiness scoring, Career Roadmap generation, Interview Question generation, and complete end-to-end platform workflows.
