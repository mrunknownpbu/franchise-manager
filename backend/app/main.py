import logging, uuid
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Header, Cookie, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from app.config import get_settings
from app.database import Base, engine, get_db
from app.models import *
from app.schemas import *
from app.services.auth import AuthService
from app.services.tmdb import TMDbClient
from app.services.radarr import RadarrClient
from app.services.collections import CollectionService
from app.services.filesystem import FilesystemAnalyzer

logging.basicConfig(level=get_settings().log_level)
Base.metadata.create_all(bind=engine)
app=FastAPI(title='Franchise Manager', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
auth=AuthService(); collections=CollectionService()

@app.on_event('startup')
def startup():
 db=next(get_db())
 try: auth.init_admin_user(db)
 finally: db.close()

def current_user(db: Session=Depends(get_db), authorization: str|None=Header(default=None), session: str|None=Cookie(default=None)):
 token=session or (authorization[7:] if authorization and authorization.lower().startswith('bearer ') else authorization)
 user=auth.verify_token(db,token) if token else None
 if not user: raise HTTPException(401,'Authentication required')
 return user

def safe(obj): return obj

@app.get('/api/health')
async def health():
 s=get_settings(); db_status='healthy'; fs='healthy'
 try:
  with Session(bind=engine) as db: db.execute(__import__('sqlalchemy').text('SELECT 1'))
 except Exception: db_status='unhealthy'
 try:
  import os; fs='healthy' if os.path.isdir(s.movie_library_path) else 'unhealthy'
 except Exception: fs='unhealthy'
 return {'status':'healthy' if db_status=='healthy' else 'degraded','database':db_status,'radarr':'unknown','tmdb':'unknown','filesystem':fs,'timestamp':datetime.utcnow()}

@app.post('/api/auth/login',response_model=LoginResponse)
def login(payload: LoginRequest, db: Session=Depends(get_db)):
 result=auth.login(db,payload.username,payload.password)
 if not result: raise HTTPException(401,'Invalid username or password')
 user, token=result
 return {'token':token,'user':user}
@app.post('/api/auth/logout')
def logout(db: Session=Depends(get_db), authorization: str|None=Header(default=None), session: str|None=Cookie(default=None)):
 token=session or (authorization[7:] if authorization and authorization.lower().startswith('bearer ') else authorization)
 return {'success': bool(token and auth.logout(db,token))}
@app.get('/api/auth/me',response_model=UserResponse)
def me(user=Depends(current_user)): return user
@app.post('/api/auth/change-password')
def change_password(payload: ChangePasswordRequest,user=Depends(current_user),db: Session=Depends(get_db)):
 if not auth.change_password(db,user.id,payload.old_password,payload.new_password): raise HTTPException(400,'Invalid current password')
 return {'success':True}

@app.get('/api/collections',response_model=list[CollectionResponse])
async def list_collections(enabled_only: bool=False, db: Session=Depends(get_db), user=Depends(current_user)): return await collections.get_collections(db,enabled_only)
@app.post('/api/collections',response_model=CollectionResponse)
async def create_collection(payload: CollectionCreate,db: Session=Depends(get_db),user=Depends(current_user)): return await collections.create_collection(db,payload)
@app.get('/api/collections/{collection_id}',response_model=CollectionDetailResponse)
async def get_collection(collection_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
 c=await collections.get_collection(db,collection_id)
 if not c: raise HTTPException(404,'Collection not found')
 c.movies=db.query(Movie).filter(Movie.collection_id==c.id).options(joinedload(Movie.state)).all()
 return c
@app.put('/api/collections/{collection_id}',response_model=CollectionResponse)
async def update_collection(collection_id:int,payload:CollectionUpdate,db:Session=Depends(get_db),user=Depends(current_user)):
 c=await collections.update_collection(db,collection_id,payload)
 if not c: raise HTTPException(404,'Collection not found')
 return c
@app.delete('/api/collections/{collection_id}')
async def delete_collection(collection_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
 if not await collections.delete_collection(db,collection_id): raise HTTPException(404,'Collection not found')
 return {'success':True}
@app.post('/api/collections/{collection_id}/sync')
@app.post('/api/collections/{collection_id}/sync-now')
async def sync_collection(collection_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
 try: return await collections.sync_collection(db,collection_id)
 except ValueError as e: raise HTTPException(404,str(e))
 except Exception as e: raise HTTPException(502,'Synchronization failed')
@app.post('/api/collections/{collection_id}/add-missing')
async def add_missing(collection_id:int, payload:BulkAddMoviesRequest,db:Session=Depends(get_db),user=Depends(current_user)):
 return await add_movies(payload,collection_id,db)

@app.get('/api/movies/{movie_id}',response_model=MovieWithStateResponse)
def movie(movie_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
 m=db.query(Movie).options(joinedload(Movie.state)).filter(Movie.id==movie_id).first()
 if not m: raise HTTPException(404,'Movie not found')
 return m
@app.post('/api/movies/{movie_id}/exclude')
async def exclude(movie_id:int,payload:ExclusionCreate,db:Session=Depends(get_db),user=Depends(current_user)):
 m=db.get(Movie,movie_id)
 if not m: raise HTTPException(404,'Movie not found')
 await collections.exclude_movie(db,m.collection_id,m.tmdb_movie_id,payload.reason); return {'success':True}
@app.delete('/api/movies/{movie_id}/exclude')
async def unexclude(movie_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
 m=db.get(Movie,movie_id)
 if not m: raise HTTPException(404,'Movie not found')
 await collections.unexclude_movie(db,m.collection_id,m.tmdb_movie_id); return {'success':True}

async def add_movies(payload, collection_id, db):
 c=db.get(Collection,collection_id)
 if not c: raise HTTPException(404,'Collection not found')
 added=skipped=existing=failed=0; errors=[]; client=RadarrClient()
 for mid in payload.movie_ids:
  m=db.query(Movie).filter(Movie.id==mid,Movie.collection_id==collection_id).first()
  if not m: failed+=1; errors.append({'movie_id':mid,'error':'not found'}); continue
  st=m.state
  if st and st.status in ('managed','existing'): skipped+=1; existing+=st.status=='existing'; continue
  try:
   data={'tmdbId':m.tmdb_movie_id,'title':m.title,'year':m.year,'qualityProfileId':c.quality_profile_id or get_settings().radarr_quality_profile_id,'rootFolderPath':c.root_folder_path or get_settings().radarr_root_folder,'monitored':True,'addOptions':{'searchForMovie':True}}
   result=await client.add_movie(data)
   if result.get('error')=='duplicate': skipped+=1
   else: added+=1
  except Exception as e: failed+=1; errors.append({'movie_id':mid,'error':str(e)})
 return {'added':added,'skipped':skipped,'existing':existing,'failed':failed,'errors':errors}
@app.post('/api/movies/{movie_id}/add')
async def add_one(movie_id:int,db:Session=Depends(get_db),user=Depends(current_user)): return await add_movies(BulkAddMoviesRequest(movie_ids=[movie_id]),db.get(Movie,movie_id).collection_id if db.get(Movie,movie_id) else 0,db)

@app.get('/api/tmdb/search/collections')
async def search_tmdb(q: str=Query(min_length=1), user=Depends(current_user)): return await TMDbClient().search_collections(q)
@app.get('/api/tmdb/collections/{collection_id}')
async def tmdb_collection(collection_id:int,user=Depends(current_user)): return await TMDbClient().get_collection(collection_id)
@app.get('/api/radarr/status')
async def radarr_status(user=Depends(current_user)): return await RadarrClient().get_system_status()
@app.get('/api/radarr/profiles')
async def profiles(user=Depends(current_user)): return await RadarrClient().get_quality_profiles()
@app.get('/api/radarr/root-folders')
async def roots(user=Depends(current_user)): return await RadarrClient().get_root_folders()
@app.get('/api/audit',response_model=list[AuditLogResponse])
def audit(limit:int=100,db:Session=Depends(get_db),user=Depends(current_user)): return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(min(limit,500)).all()
@app.get('/api/sync/runs',response_model=list[SyncRunResponse])
def runs(limit:int=50,db:Session=Depends(get_db),user=Depends(current_user)): return db.query(SyncRun).order_by(SyncRun.started_at.desc()).limit(min(limit,200)).all()
@app.get('/api/jobs',response_model=list[JobResponse])
def jobs(db:Session=Depends(get_db),user=Depends(current_user)): return db.query(Job).order_by(Job.started_at.desc()).limit(50).all()
@app.get('/api/jobs/{job_id}',response_model=JobResponse)
def job(job_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
 j=db.query(Job).filter(Job.job_id==job_id).first()
 if not j: raise HTTPException(404,'Job not found')
 return j

@app.get('/api/settings')
def settings_view(user=Depends(current_user)):
    s = get_settings()
    return {
        'app_port': s.app_port, 'movie_library_path': s.movie_library_path,
        'radarr_url': s.radarr_url, 'sync_enabled': s.sync_enabled,
        'sync_interval_hours': s.sync_interval_hours,
        'auto_add_missing': s.auto_add_missing,
        'match_confidence_threshold': s.match_confidence_threshold,
        'tmdb_configured': bool(s.tmdb_api_key),
        'radarr_configured': bool(s.radarr_url and s.radarr_api_key),
    }

@app.post('/api/settings/rebuild-index')
def rebuild_index(user=Depends(current_user)):
    try:
        movies = FilesystemAnalyzer().scan_library()
        return {'status': 'completed', 'movies_indexed': len(movies)}
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.post('/api/settings/test-tmdb')
async def test_tmdb(user=Depends(current_user)):
    return {'connected': await TMDbClient().test_connection()}

@app.post('/api/settings/test-radarr')
async def test_radarr(user=Depends(current_user)):
    return {'connected': await RadarrClient().test_connection()}

@app.get('/',include_in_schema=False)
async def index():
 from pathlib import Path
 p=Path(__file__).parent/'static'/'index.html'
 if p.exists(): return FileResponse(p)
 return {'name':'Franchise Manager','docs':'/docs'}
