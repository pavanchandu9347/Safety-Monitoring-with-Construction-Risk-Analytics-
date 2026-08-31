from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.models import Project, Site, Zone
from app.schemas.schemas import ProjectCreate, ProjectResponse, SiteCreate, SiteResponse, ZoneCreate, ZoneResponse

router = APIRouter()


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    import uuid
    project = Project(id=str(uuid.uuid4()), **data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/sites", response_model=list[SiteResponse])
def list_sites(db: Session = Depends(get_db)):
    return db.query(Site).all()


@router.get("/sites/{site_id}", response_model=SiteResponse)
def get_site(site_id: str, db: Session = Depends(get_db)):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.post("/sites", response_model=SiteResponse, status_code=201)
def create_site(data: SiteCreate, db: Session = Depends(get_db)):
    import uuid
    site = Site(id=str(uuid.uuid4()), **data.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.get("/sites/{site_id}/zones", response_model=list[ZoneResponse])
def list_zones(site_id: str, db: Session = Depends(get_db)):
    return db.query(Zone).filter(Zone.site_id == site_id).all()


@router.post("/zones", response_model=ZoneResponse, status_code=201)
def create_zone(data: ZoneCreate, db: Session = Depends(get_db)):
    import uuid
    zone = Zone(id=str(uuid.uuid4()), **data.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone
