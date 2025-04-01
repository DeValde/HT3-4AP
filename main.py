from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import Base, engine
import models
import schemas
import crud
import auth
import redis_client
from auth import get_current_user, get_current_user_optional, create_access_token, get_password_hash, verify_password
from datetime import timedelta, datetime
from fastapi.security import OAuth2PasswordRequestForm

app = FastAPI(
    title="URL Shortener API",
    description="Service to shorten URLs, track analytics, and manage links.",
    version="1.0.0"
)
#simple html ui
templates = Jinja2Templates(directory="templates")
Base.metadata.create_all(bind=engine)


@app.get("/")
def read_root():
    return {"message": "Welcome to the URL Shortener API. Visit /ui for the web interface."}


@app.get("/ui", response_class=HTMLResponse)
def ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/users/register", response_model=schemas.UserResponse)
def register(user_in: schemas.UserCreate, db: Session = Depends(auth.get_db)):
    if db.query(models.User).filter(models.User.username == user_in.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user_in.password)
    user = models.User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_password
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(auth.get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/links/shorten", response_model=schemas.LinkResponse)
def create_short_link(link_in: schemas.LinkCreate, db: Session = Depends(auth.get_db),
                      current_user: models.User = Depends(get_current_user_optional)):
    link = crud.create_link(db, link_in, owner_id=current_user.id if current_user else None)
    return link


# Place the search route before the dynamic route so that /links/search is matched correctly.
@app.get("/links/search", response_model=list[schemas.LinkResponse])
def search_links(original_url: str, db: Session = Depends(auth.get_db)):
    links = crud.search_link_by_original(db, original_url)
    return links


@app.get("/links/{short_code}/stats", response_model=schemas.LinkStats)
def get_link_statistics(short_code: str, db: Session = Depends(auth.get_db)):
    link = crud.get_link_stats(db, short_code)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    return link


@app.get("/links/{short_code}")
def redirect_to_url(short_code: str, db: Session = Depends(auth.get_db)):
    cache_key = f"link:{short_code}"
    cached_url = redis_client.r.get(cache_key)
    if cached_url:
        link = crud.get_link_by_code(db, short_code)
        if link:
            crud.increment_click(db, link)
        return RedirectResponse(url=cached_url)

    link = crud.get_link_by_code(db, short_code)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    if link.expires_at and datetime.utcnow() > link.expires_at:
        raise HTTPException(status_code=410, detail="Link expired")

    crud.increment_click(db, link)
    redis_client.r.set(cache_key, link.original_url, ex=60 * 60)
    return RedirectResponse(url=link.original_url)


@app.put("/links/{short_code}", response_model=schemas.LinkResponse)
def update_link(short_code: str, link_in: schemas.LinkUpdate, db: Session = Depends(auth.get_db),
                current_user: models.User = Depends(get_current_user)):
    link = crud.update_link(db, short_code, link_in, current_user)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found or not authorized")
    redis_client.r.delete(f"link:{short_code}")
    return link


@app.delete("/links/{short_code}")
def delete_link(short_code: str, db: Session = Depends(auth.get_db),
                current_user: models.User = Depends(get_current_user)):
    link = crud.delete_link(db, short_code, current_user)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found or not authorized")
    redis_client.r.delete(f"link:{short_code}")
    return {"detail": "Link deleted successfully"}