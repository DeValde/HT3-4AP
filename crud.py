from sqlalchemy.orm import Session
from models import Link, User
from schemas import LinkCreate, LinkUpdate
from utils import generate_short_code
from datetime import datetime
from pydantic import HttpUrl

def normalize_url(url: str) -> str:
    try:
        return str(HttpUrl(url=url))
    except Exception:
        return url

def create_link(db: Session, link_in: LinkCreate, owner_id: int = None):
    short_code = link_in.custom_alias if link_in.custom_alias else generate_short_code()
    while db.query(Link).filter(Link.short_code == short_code).first():
        short_code = generate_short_code()

    normalized_url = normalize_url(str(link_in.original_url))
    link = Link(
        original_url=normalized_url,
        short_code=short_code,
        expires_at=link_in.expires_at,
        owner_id=owner_id
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link

def get_link_by_code(db: Session, short_code: str):
    return db.query(Link).filter(Link.short_code == short_code).first()

def update_link(db: Session, short_code: str, link_in: LinkUpdate, user: User):
    link = get_link_by_code(db, short_code)
    if not link:
        return None
    if link.owner_id != user.id:
        return None
    if link_in.original_url:
        link.original_url = normalize_url(str(link_in.original_url))
    if link_in.expires_at:
        link.expires_at = link_in.expires_at
    db.commit()
    db.refresh(link)
    return link

def delete_link(db: Session, short_code: str, user: User):
    link = get_link_by_code(db, short_code)
    if not link:
        return None
    if link.owner_id != user.id:
        return None
    db.delete(link)
    db.commit()
    return link

def increment_click(db: Session, link: Link):
    link.click_count += 1
    link.last_accessed = datetime.utcnow()
    db.commit()
    db.refresh(link)
    return link

def get_link_stats(db: Session, short_code: str):
    return get_link_by_code(db, short_code)

def search_link_by_original(db: Session, original_url: str):
    normalized = normalize_url(original_url)
    return db.query(Link).filter(Link.original_url == normalized).all()