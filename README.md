# Franchise Manager

A production-grade, self-hosted web application for managing movie franchises and collections using TMDb as the authoritative source and Radarr as the acquisition engine.

## Architecture Overview

```
TMDb Collection Metadata
        ↓
  Franchise Manager
  ├─ Collection Management
  ├─ Movie Matching Engine
  ├─ Sync Engine
  └─ Acquisition Controller
        ↓
   ┌────┴────┐
   ↓         ↓
 Radarr   Filesystem (Read-Only)
   ↓         ↓
   └────┬────┘
        ↓
  Movie Library
        ↓
   Jellyfin
```

## Features

- **TMDb Integration**: Search and sync movie collections from The Movie Database
- **Radarr Integration**: Query and manage movies through Radarr
- **Intelligent Movie Matching**: Multi-factor matching engine with confidence scoring
- **Filesystem Analysis**: Read-only inspection of existing movie library
- **Movie State Classification**: 
  - Managed by Radarr
  - Existing (Unmanaged)
  - Missing
  - Excluded
  - Needs Review
- **Collection Monitoring**: Automatic periodic synchronization of monitored collections
- **Bulk Operations**: Add multiple missing movies at once
- **Audit Logging**: Complete audit trail of all operations
- **Modern Web UI**: Responsive React-based interface
- **Background Jobs**: Async processing for long-running operations
- **Authentication**: Secure local authentication with session management
- **Health Checks**: Real-time system health monitoring

## Technology Stack

### Backend
- **Framework**: Python 3.11+ with FastAPI
- **Database**: SQLite with SQLAlchemy ORM
- **Async**: APScheduler for background jobs
- **HTTP**: httpx for external API calls
- **Validation**: Pydantic

### Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **UI Components**: Custom components with Headless UI
- **HTTP Client**: Axios

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OR: Python 3.11+, Node.js 18+, npm

### Docker Deployment

```bash
# Clone the repository
git clone https://github.com/mrunknownpbu/franchise-manager.git
cd franchise-manager

# Copy and edit environment configuration
cp .env.example .env
# Edit .env with your configuration

# Start the application
docker compose up -d --build

# Application available at http://localhost:8787
```

### Local Development

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp ../.env.example .env
# Edit .env with your configuration

# Run migrations
python -m alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev

# Frontend available at http://localhost:5173
```

## Configuration

### Environment Variables

```env
# Application
APP_PORT=8787
TZ=UTC

# Database
DATABASE_PATH=/config/franchise-manager.db

# TMDb
TMDB_API_KEY=your_api_key_here

# Radarr
RADARR_URL=http://radarr:7878
RADARR_API_KEY=your_api_key_here
RADARR_ROOT_FOLDER=/movies
RADARR_QUALITY_PROFILE_ID=1

# Filesystem
MOVIE_LIBRARY_PATH=/movies

# Authentication
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme

# Synchronization
SYNC_ENABLED=true
SYNC_INTERVAL_HOURS=6

# Logging
LOG_LEVEL=INFO
```

See `.env.example` for all available options.

## Getting TMDb API Key

1. Visit https://www.themoviedb.org/settings/api
2. Create an account or login
3. Generate an API key
4. Copy the key to `TMDB_API_KEY` in `.env`

## Configuring Radarr

1. In Radarr, navigate to **Settings** → **General** → **API Key**
2. Copy the API key to `RADARR_API_KEY` in `.env`
3. Retrieve root folder path from Radarr API or UI
4. Retrieve quality profile ID from Radarr

## Configuring Movie Library Path

Set `MOVIE_LIBRARY_PATH` to the root directory containing your movies. The application will:

- Scan the directory read-only
- Extract metadata from folder/file names
- Match movies using TMDb IDs, IMDb IDs, and title normalization
- NEVER delete, rename, move, or modify files

## First Login

1. Start the application
2. Navigate to `http://localhost:8787`
3. Login with credentials from `ADMIN_USERNAME` and `ADMIN_PASSWORD`
4. You will be prompted to change your password
5. Complete initial setup in the Settings page

## Usage

### Adding a Collection

1. Navigate to **Collections**
2. Click **Search Collection**
3. Search for a movie franchise (e.g., "John Wick")
4. Select the collection to view all movies
5. Movies will be classified as:
   - **Managed**: Already in Radarr
   - **Existing**: On filesystem but not in Radarr
   - **Missing**: Not found anywhere
   - **Excluded**: Manually excluded from acquisition

### Adding Missing Movies

1. View a collection
2. Select missing movies you want to add
3. Click **Add Selected**
4. Confirm the operation
5. Movies will be added to Radarr with configured settings

### Monitoring Collections

1. View a collection
2. Click **Monitor Collection**
3. Configure:
   - Automatic addition of new movies
   - Quality profile
   - Root folder
   - Sync interval
4. The collection will sync automatically on schedule

### Manual Synchronization

1. Click **Sync Now** on a collection, or
2. Click **Sync All Collections** on the dashboard
3. Monitor progress in the **Jobs** section

## Movie Matching Logic

The matching engine uses multiple identifiers with confidence scoring:

1. **Very High Confidence** (95%+)
   - TMDb ID exact match
   - IMDb ID exact match

2. **High Confidence** (80%+)
   - Title + year exact match (normalized)
   - TMDb ID in filename

3. **Medium Confidence** (60%+)
   - Normalized title + year match
   - IMDb ID in filename

4. **Insufficient** (<60%)
   - Fuzzy title-only matching
   - Movies below threshold marked as "Needs Review"

### Supported Folder Structures

```
Movie Title (2020)
Movie Title (2020) {tmdb-12345}
Movie Title (2020) {imdb-tt1234567}
Movie.Title.2020
movie_title_2020
```

Normalization includes:
- Case-insensitivity
- Punctuation removal
- Whitespace/underscore/hyphen standardization
- Diacritic removal
- Apostrophe handling

## Filesystem Analysis

The application performs **read-only** analysis of your movie library:

- Scans folder structures
- Extracts metadata from folder/file names
- Maintains an indexed inventory for fast lookups
- Detects existing movies not in Radarr
- Determines acquisition eligibility

### Rebuild Library Index

1. Navigate to **Settings**
2. Click **Rebuild Library Index**
3. Monitor progress

This is useful after:
- Adding/removing movies manually
- Changing the library path
- Detecting matching issues

## Duplicate Protection

Before adding any movie to Radarr, the system verifies:

1. TMDb ID against Radarr catalog
2. IMDb ID against Radarr catalog
3. Normalized title + year against Radarr
4. Filesystem for existing files
5. Application database for prior acquisitions

If a movie exists on disk: **Classified as "Existing — Unmanaged", NOT acquired**

## Automatic Synchronization

For monitored collections:

1. On configured schedule (default: 6 hours)
2. Query TMDb for current movies
3. Compare against Radarr
4. Analyze filesystem
5. Apply user exclusions
6. Identify genuinely missing movies
7. Add missing movies if automatic acquisition enabled
8. Record all actions in audit log

No movies are ever deleted or modified.

## Audit Log

Every mutation is recorded:

- Collection added/removed
- Sync started/completed
- Movie added to Radarr
- Movie skipped (existing)
- Movie excluded
- Settings changed

Filter by:
- Date range
- Action type
- Collection
- Result (success/failure)

## Error Handling

The system gracefully handles:

- **TMDb Unavailable**: Last known state preserved, clear status indicator
- **Radarr Unavailable**: No duplicate acquisition, clear status indicator
- **Rate Limiting**: Exponential backoff, bounded retries
- **Invalid Credentials**: Clear error messages, no silent failures
- **Filesystem Issues**: Graceful degradation with status reporting

## Security

- API keys never exposed to frontend
- Passwords hashed using bcrypt
- Session cookies secure and httpOnly
- CSRF protection on state-changing operations
- Input validation on all endpoints
- SQL injection protection via SQLAlchemy ORM
- No arbitrary filesystem access
- Read-only filesystem operations
- No shell execution from user input
- No Docker socket requirement

## Health Checks

```bash
curl http://localhost:8787/api/health
```

Response:
```json
{
  "status": "healthy",
  "database": "healthy",
  "radarr": "healthy",
  "tmdb": "healthy",
  "filesystem": "healthy"
}
```

## Logging

Structured application logs with levels:

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARN**: Warning conditions that should be reviewed
- **ERROR**: Error conditions requiring attention

Logs are written to stdout and optionally to file.

Secrets (API keys, passwords, tokens) are never logged.

## Database Schema

### collections
- `id`: Primary key
- `tmdb_collection_id`: TMDb collection ID (unique)
- `name`: Collection name
- `poster_path`, `backdrop_path`: TMDb media
- `enabled`: Is monitoring enabled
- `auto_add_missing`: Automatically add missing movies
- `quality_profile_id`: Radarr quality profile
- `root_folder_path`: Radarr root folder
- `monitoring_policy`: Monitoring configuration
- `sync_interval`: Hours between syncs
- `last_sync_at`: Last successful sync timestamp
- `created_at`, `updated_at`: Audit timestamps

### movies
- `id`: Primary key
- `collection_id`: Foreign key to collections
- `tmdb_movie_id`: TMDb movie ID
- `title`, `release_date`, `year`: Movie metadata
- `imdb_id`: IMDb ID for alternate matching
- `poster_path`, `backdrop_path`: Media
- `overview`: Description
- `created_at`, `updated_at`: Audit timestamps

### movie_states
- `id`: Primary key
- `movie_id`: Foreign key to movies
- `radarr_movie_id`: Radarr ID if managed
- `radarr_managed`: Boolean state
- `filesystem_exists`: Boolean state
- `filesystem_path`: Path on disk if found
- `status`: Current classification
- `match_confidence`: Confidence percentage
- `last_checked_at`: Last analysis timestamp

### exclusions
- `id`: Primary key
- `collection_id`: Foreign key
- `tmdb_movie_id`: Excluded movie
- `reason`: User-provided reason
- `created_at`: Exclusion timestamp

### sync_runs
- `id`: Primary key
- `collection_id`: Foreign key
- `started_at`, `completed_at`: Timestamps
- `status`: QUEUED|RUNNING|COMPLETED|FAILED
- `movies_discovered`: Count
- `movies_added`: Count
- `movies_skipped`: Count
- `movies_failed`: Count
- `error`: Error message if failed

### audit_logs
- `id`: Primary key
- `timestamp`: When action occurred
- `action`: Action type
- `collection_id`: Affected collection
- `tmdb_movie_id`: Affected movie
- `radarr_movie_id`: Affected movie in Radarr
- `details`: Action details (JSON)
- `result`: SUCCESS|FAILED

### users
- `id`: Primary key
- `username`: Unique username
- `password_hash`: Bcrypt hash
- `is_admin`: Admin privileges
- `created_at`, `updated_at`: Timestamps

### sessions
- `id`: Primary key
- `user_id`: Foreign key to users
- `token`: Session token
- `expires_at`: Expiration timestamp
- `created_at`: Creation timestamp

### jobs
- `id`: Primary key
- `job_id`: Background job ID
- `name`: Job name
- `status`: QUEUED|RUNNING|COMPLETED|FAILED
- `progress`: Percentage complete
- `total_steps`: Total steps
- `current_step`: Current step
- `result`: Job result (JSON)
- `error`: Error message if failed
- `started_at`, `completed_at`: Timestamps

## REST API Endpoints

### Health & Status
```
GET  /api/health
```

### Authentication
```
POST /api/auth/login
POST /api/auth/logout
POST /api/auth/change-password
GET  /api/auth/me
```

### Collections
```
GET    /api/collections
POST   /api/collections
GET    /api/collections/{id}
DELETE /api/collections/{id}
PUT    /api/collections/{id}
```

### Collection Operations
```
POST /api/collections/{id}/sync
POST /api/collections/{id}/sync-now
POST /api/collections/{id}/add-missing
```

### Movies
```
GET    /api/movies/{id}
POST   /api/movies/{id}/add
POST   /api/movies/{id}/exclude
DELETE /api/movies/{id}/exclude
```

### TMDb
```
GET /api/tmdb/search/collections?q=
GET /api/tmdb/collections/{id}
```

### Radarr Status
```
GET /api/radarr/status
GET /api/radarr/profiles
GET /api/radarr/root-folders
```

### Settings
```
GET  /api/settings
PUT  /api/settings
POST /api/settings/test-tmdb
POST /api/settings/test-radarr
POST /api/settings/rebuild-index
```

### Audit & History
```
GET /api/audit?from=&to=&action=&result=
GET /api/sync/runs
GET /api/jobs
GET /api/jobs/{id}
```

## Troubleshooting

### TMDb Not Connected
- Verify `TMDB_API_KEY` is valid
- Check rate limits: TMDb limits to 40 requests/10 seconds
- Verify network connectivity

### Radarr Not Connected
- Verify `RADARR_URL` is accessible
- Verify `RADARR_API_KEY` is correct
- Check Radarr logs for errors
- Ensure Radarr quality profiles exist

### Movies Not Detected
- Verify `MOVIE_LIBRARY_PATH` is correct and readable
- Check folder naming convention
- Run "Rebuild Library Index"
- Check logs for matching errors

### Movies Showing as "Needs Review"
- Check folder name format
- Add TMDb ID or IMDb ID to folder name
- Adjust match confidence threshold in Settings
- Manually review and exclude/confirm

### Duplicate Prevention Not Working
- Run "Rebuild Library Index"
- Check audit log for prior acquisitions
- Verify Radarr integration is working
- Check filesystem for existing files

## Database Backup

```bash
# Backup
cp /config/franchise-manager.db /path/to/backup/franchise-manager.db.backup

# Restore
cp /path/to/backup/franchise-manager.db.backup /config/franchise-manager.db
docker compose restart
```

## Performance Optimization

The application uses:

- **Caching**: TMDb metadata caching with configurable TTL
- **Indexing**: Database indexes on frequently queried fields
- **Batch Operations**: Bulk Radarr operations where supported
- **Background Processing**: Async jobs for long operations
- **Incremental Sync**: Only sync changed collections
- **Filesystem Index**: Indexed inventory for fast lookups

For large libraries (10,000+ movies):

1. Increase `SYNC_INTERVAL_HOURS` to reduce frequency
2. Monitor background job progress
3. Consider horizontal scaling with multiple sync workers (future feature)

## Development

### Running Tests

```bash
cd backend
pytest tests/ -v

cd ../frontend
npm run test
```

### Code Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Configuration management
│   ├── database/               # Database setup
│   ├── models/                 # SQLAlchemy ORM models
│   ├── schemas/                # Pydantic request/response schemas
│   ├── api/                    # API route handlers
│   ├── services/               # Business logic
│   │   ├── tmdb.py             # TMDb integration
│   │   ├── radarr.py           # Radarr integration
│   │   ├── filesystem.py       # Filesystem analysis
│   │   ├── matching.py         # Movie matching engine
│   │   ├── collections.py      # Collection management
│   │   └── sync.py             # Synchronization logic
│   ├── jobs/                   # Background job definitions
│   └── auth/                   # Authentication & authorization

frontend/
├── src/
│   ├── components/             # Reusable React components
│   ├── pages/                  # Page components
│   ├── services/               # API client services
│   ├── hooks/                  # Custom React hooks
│   ├── types/                  # TypeScript type definitions
│   ├── App.tsx                 # Main application component
│   └── main.tsx                # Entry point
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Support

For issues, feature requests, or questions:
- Check existing GitHub issues
- Review troubleshooting section
- Check application logs
- Review audit log for operation history

## Roadmap

Future enhancements:

- [ ] Jellyfin collection sync
- [ ] Multi-user collections
- [ ] Advanced matching heuristics
- [ ] Sonarr integration for TV shows
- [ ] Notification system (Discord, Webhooks)
- [ ] Performance analytics
- [ ] GraphQL API
- [ ] Database replication/clustering
- [ ] Advanced scheduling rules
- [ ] Machine learning-based matching
