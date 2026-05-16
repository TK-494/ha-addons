from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import Category
from ..schemas import CategoryCreate, CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])

DEFAULT_CATEGORIES = [
    {"name": "Boodschappen", "color": "#22c55e", "icon": "🛒",
     "keywords": "albert heijn,jumbo,lidl,aldi,plus supermarkt,dirk,spar,coop,deka"},
    {"name": "Inkomen", "color": "#6366f1", "icon": "💰",
     "keywords": "salaris,loon,uitkering,vakantiegeld,toeslagen"},
    {"name": "Wonen", "color": "#f59e0b", "icon": "🏠",
     "keywords": "hypotheek,huur,woningcorp,eigen haard,ymere"},
    {"name": "Energie", "color": "#ef4444", "icon": "⚡",
     "keywords": "vattenfall,eneco,essent,nuon,greenchoice,energie"},
    {"name": "Zorgverzekering", "color": "#ec4899", "icon": "🏥",
     "keywords": "zilveren kruis,vgz,cz,menzis,achmea,dsw"},
    {"name": "Telefoon/Internet", "color": "#8b5cf6", "icon": "📱",
     "keywords": "kpn,t-mobile,vodafone,ziggo,odido,tele2"},
    {"name": "Transport", "color": "#06b6d4", "icon": "🚌",
     "keywords": "ns,ov-chipkaart,htm,gvb,ret,connexxion,parking"},
    {"name": "Restaurant & Café", "color": "#f97316", "icon": "🍽️",
     "keywords": "mcdonalds,burger king,kfc,pizza,restaurant,cafe,thuisbezorgd"},
    {"name": "Sport & Fitness", "color": "#84cc16", "icon": "💪",
     "keywords": "basic-fit,fitness,sportschool,gym,zwembad"},
    {"name": "Kleding", "color": "#a855f7", "icon": "👗",
     "keywords": "h&m,zara,primark,c&a,van haren,wehkamp,zalando"},
    {"name": "Online Shopping", "color": "#0ea5e9", "icon": "🛍️",
     "keywords": "bol.com,amazon,coolblue,mediamarkt,paypal,klarna"},
    {"name": "Zorg & Apotheek", "color": "#14b8a6", "icon": "💊",
     "keywords": "apotheek,huisarts,tandarts,ziekenhuis,fysiotherap,kruidvat,etos"},
    {"name": "Abonnementen", "color": "#f43f5e", "icon": "📺",
     "keywords": "spotify,netflix,disney,videoland,adobe,microsoft,apple,google"},
    {"name": "Bank & Verzekering", "color": "#64748b", "icon": "🏦",
     "keywords": "rente,kosten rekening,abonnement rabobank,interpolis,centraal beheer"},
    {"name": "Overig", "color": "#94a3b8", "icon": "📋", "keywords": ""},
]


@router.get("/", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()


@router.post("/", response_model=CategoryOut)
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    db_cat = Category(**category.model_dump())
    db.add(db_cat)
    db.commit()
    db.refresh(db_cat)
    return db_cat


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, category: CategoryCreate, db: Session = Depends(get_db)):
    db_cat = db.query(Category).filter(Category.id == category_id).first()
    if not db_cat:
        raise HTTPException(status_code=404, detail="Category not found")
    for key, val in category.model_dump().items():
        setattr(db_cat, key, val)
    db.commit()
    db.refresh(db_cat)
    return db_cat


@router.delete("/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    db_cat = db.query(Category).filter(Category.id == category_id).first()
    if not db_cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(db_cat)
    db.commit()
    return {"ok": True}


def seed_default_categories(db: Session):
    if db.query(Category).count() == 0:
        for cat in DEFAULT_CATEGORIES:
            db.add(Category(**cat))
        db.commit()
