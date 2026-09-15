import os
from app.services.matching import MovieMatcher

def test_exact_tmdb_id_is_perfect():
 m=MovieMatcher(); result=m.match_tmdb_to_radarr({'id':42,'title':'A','release_date':'2020-01-01'},[{'tmdbId':42,'title':'Different'}])
 assert result[1] == 100

def test_title_year_matching_and_normalization():
 m=MovieMatcher(); result=m.match_tmdb_to_filesystem({'id':1,'title':'Amelie','release_date':'2001-01-01'},[{'title':'Amelie','year':2001,'path':'/movies/Amelie'}])
 assert result and result[1] == 90

def test_weak_match_is_rejected():
 m=MovieMatcher(); assert m.match_tmdb_to_radarr({'id':1,'title':'Alien','release_date':'1979-01-01'},[{'title':'Completely Different','year':1986}]) is None


