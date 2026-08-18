from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime
import csv
import io
from ..core.database import get_db
from ..core.security import hash_password
from ..models.user import User, UserRole
from ..models.vessel import Vessel
from ..models.fleet import Fleet
from ..models.question import QuestionBank
from ..models.assignment import Assignment
from ..models.template import Template
from ..models.ca_library import CALibrary
from ..models.session import InspectionSession
from ..models.inspection import Inspection
from ..models.report import Report
from ..models.capa import CAPA
from ..models.audit_log import AuditLog
from ..models.profile import Profile
from .auth import get_current_user

router = APIRouter(prefix="/api", tags=["Admin"])

# --- Helper: write audit log ---
def log_action(db, user, action, entity=None, entity_id=None, details=None):
    try:
        entry = AuditLog(
            user_id=user.id if user else None,
            user_name=user.name if user else None,
            action=action, entity=entity, entity_id=entity_id, details=details,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()

# ============ FLEETS ============
@router.get("/admin/fleets")
def list_fleets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    fleets = db.query(Fleet).all()
    all_vessels = db.query(Vessel).all()
    data = []
    for f in fleets:
        count = sum(1 for v in all_vessels if str(v.fleet_id) == str(f.id) or str(v.fleet_id) == str(f.name))
        data.append({"id": f.id, "name": f.name, "description": f.description, "vessel_count": count})
    return {"success": True, "data": data}

@router.post("/admin/fleets")
def create_fleet(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    fleet = Fleet(name=payload.get("name"), description=payload.get("description", ""))
    db.add(fleet)
    db.commit()
    db.refresh(fleet)
    log_action(db, user, "created fleet", "fleet", fleet.id, fleet.name)
    return {"success": True, "data": {"id": fleet.id, "name": fleet.name, "description": fleet.description}}

@router.patch("/admin/fleets/{fleet_id}")
def update_fleet(fleet_id: int, payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    fleet = db.query(Fleet).filter(Fleet.id == fleet_id).first()
    if not fleet:
        return {"success": False, "message": "Fleet not found"}
    for key in ["name", "description"]:
        if key in payload:
            setattr(fleet, key, payload[key])
    db.commit()
    db.refresh(fleet)
    log_action(db, user, "updated fleet", "fleet", fleet.id, fleet.name)
    return {"success": True, "data": {"id": fleet.id, "name": fleet.name, "description": fleet.description}}

@router.delete("/admin/fleets/{fleet_id}")
def delete_fleet(fleet_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    fleet = db.query(Fleet).filter(Fleet.id == fleet_id).first()
    if not fleet:
        return {"success": False, "message": "Fleet not found"}
    db.delete(fleet)
    db.commit()
    log_action(db, user, "deleted fleet", "fleet", fleet_id)
    return {"success": True, "message": "Fleet deleted"}

# ============ VESSELS ============
@router.get("/admin/vessels")
def list_vessels(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    vessels = db.query(Vessel).all()
    return {"success": True, "data": [
        {
            "id": v.id, "name": v.name, "imo": v.imo, "type": v.vessel_type,
            "flag": v.flag, "operator": v.operator, "build_year": v.build_year,
            "fleet_id": v.fleet_id,
        } for v in vessels
    ]}

@router.post("/admin/vessels")
def create_vessel(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    existing = db.query(Vessel).filter(Vessel.imo == payload.get("imo")).first()
    if existing:
        return {"success": False, "message": "Vessel with this IMO already exists"}
    vessel = Vessel(
        name=payload.get("name"),
        imo=payload.get("imo"),
        vessel_type=payload.get("type"),
        flag=payload.get("flag"),
        operator=payload.get("operator"),
        build_year=payload.get("build_year"),
        fleet_id=payload.get("fleet_id"),
    )
    db.add(vessel)
    db.commit()
    db.refresh(vessel)
    log_action(db, user, "created vessel", "vessel", vessel.id, vessel.name)
    return {"success": True, "data": {
        "id": vessel.id, "name": vessel.name, "imo": vessel.imo,
        "type": vessel.vessel_type, "flag": vessel.flag,
        "operator": vessel.operator, "build_year": vessel.build_year,
        "fleet_id": vessel.fleet_id,
    }}

@router.patch("/admin/vessels/{vessel_id}")
def update_vessel(vessel_id: int, payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    vessel = db.query(Vessel).filter(Vessel.id == vessel_id).first()
    if not vessel:
        return {"success": False, "message": "Vessel not found"}
    if "name" in payload: vessel.name = payload["name"]
    if "imo" in payload: vessel.imo = payload["imo"]
    if "type" in payload: vessel.vessel_type = payload["type"]
    if "flag" in payload: vessel.flag = payload["flag"]
    if "operator" in payload: vessel.operator = payload["operator"]
    if "build_year" in payload: vessel.build_year = payload["build_year"]
    if "fleet_id" in payload: vessel.fleet_id = payload["fleet_id"]
    db.commit()
    db.refresh(vessel)
    log_action(db, user, "updated vessel", "vessel", vessel.id, vessel.name)
    return {"success": True, "data": {
        "id": vessel.id, "name": vessel.name, "imo": vessel.imo,
        "type": vessel.vessel_type, "flag": vessel.flag,
        "operator": vessel.operator, "build_year": vessel.build_year,
        "fleet_id": vessel.fleet_id,
    }}

@router.delete("/admin/vessels/{vessel_id}")
def delete_vessel(vessel_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    vessel = db.query(Vessel).filter(Vessel.id == vessel_id).first()
    if not vessel:
        return {"success": False, "message": "Vessel not found"}
    db.delete(vessel)
    db.commit()
    log_action(db, user, "deleted vessel", "vessel", vessel_id)
    return {"success": True, "message": "Vessel deleted"}

# ============ QUESTION BANK ============
@router.get("/admin/questions")
def list_questions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    questions = db.query(QuestionBank).all()
    return {"success": True, "data": [
        {
            "id": q.id, "question": q.question, "sub_number": q.sub_number,
            "category": q.category, "sub_area": q.sub_area, "severity": q.severity,
            "type": q.type, "evidence_required": q.evidence_required,
            "guide_to_inspection": q.guide_to_inspection,
        } for q in questions
    ]}

@router.post("/admin/questions")
def create_question(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = QuestionBank(
        question=payload.get("question"),
        sub_number=payload.get("sub_number"),
        category=payload.get("category"),
        sub_area=payload.get("sub_area"),
        severity=payload.get("severity"),
        type=payload.get("type"),
        evidence_required=payload.get("evidence_required", False),
        guide_to_inspection=payload.get("guide_to_inspection"),
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    log_action(db, user, "created question", "question", q.id)
    return {"success": True, "data": {
        "id": q.id, "question": q.question, "sub_number": q.sub_number,
        "category": q.category, "sub_area": q.sub_area, "severity": q.severity,
        "type": q.type, "evidence_required": q.evidence_required,
        "guide_to_inspection": q.guide_to_inspection,
    }}

@router.patch("/admin/questions/{question_id}")
def update_question(question_id: int, payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(QuestionBank).filter(QuestionBank.id == question_id).first()
    if not q:
        return {"success": False, "message": "Question not found"}
    for key in ["question", "sub_number", "category", "sub_area", "severity", "type", "evidence_required", "guide_to_inspection"]:
        if key in payload:
            setattr(q, key, payload[key])
    db.commit()
    db.refresh(q)
    log_action(db, user, "updated question", "question", q.id)
    return {"success": True, "data": {"id": q.id, "question": q.question}}

@router.delete("/admin/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(QuestionBank).filter(QuestionBank.id == question_id).first()
    if not q:
        return {"success": False, "message": "Question not found"}
    db.delete(q)
    db.commit()
    log_action(db, user, "deleted question", "question", question_id)
    return {"success": True, "message": "Question deleted"}

@router.post("/admin/questions/bulk-delete")
def bulk_delete_questions(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ids = payload.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return {"success": True, "deleted": 0}
    deleted = db.query(QuestionBank).filter(QuestionBank.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    log_action(db, user, f"bulk deleted {deleted} questions", "question")
    return {"success": True, "deleted": deleted}

@router.post("/admin/questions/bulk-upload")
async def bulk_upload_questions(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    count = 0
    skipped = 0

    def norm_key(k: str) -> str:
        # "SUB NO", "Sub Number", "sub_number" -> "subno" / "subnumber"
        return (k or "").strip().lower().replace(" ", "").replace("_", "").replace(".", "")

    def get_val(row_n: dict, *names) -> str:
        for n in names:
            v = row_n.get(n)
            if v is not None and str(v).strip() != "":
                return str(v).strip()
        return ""

    for row in reader:
        row_n = {norm_key(k): v for k, v in row.items()}
        question_text = get_val(row_n, "question", "questions", "questiontext")
        if not question_text:
            skipped += 1
            continue
        q = QuestionBank(
            question=question_text,
            sub_number=get_val(row_n, "subnumber", "subno", "subnum", "number") or None,
            category=get_val(row_n, "category", "section", "area") or None,
            sub_area=get_val(row_n, "subarea", "subsection") or None,
            severity=get_val(row_n, "severity", "risk") or None,
            type=get_val(row_n, "type", "questiontype", "answertype") or None,
            evidence_required=get_val(row_n, "evidencerequired", "evidence").lower() in ("true", "yes", "1"),
            guide_to_inspection=get_val(row_n, "guidetoinspection", "guide", "guidance") or None,
        )
        db.add(q)
        count += 1
    db.commit()
    log_action(db, user, f"bulk uploaded {count} questions", "question")
    return {"success": True, "message": f"{count} questions uploaded", "imported": count, "skipped": skipped}

# ============ TEMPLATES ============
@router.get("/admin/templates")
def list_templates(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    templates = db.query(Template).all()
    return {"success": True, "data": [
        {
            "id": t.id, "name": t.name, "description": t.description,
            "version": t.version, "sections": t.sections or [],
        } for t in templates
    ]}

@router.post("/admin/templates")
def create_template(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    template = Template(
        name=payload.get("name"),
        description=payload.get("description", ""),
        version=payload.get("version", "1.0"),
        sections=payload.get("sections", []),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    log_action(db, user, "created template", "template", template.id, template.name)
    return {"success": True, "data": {
        "id": template.id, "name": template.name,
        "description": template.description, "version": template.version,
        "sections": template.sections or [],
    }}

@router.patch("/admin/templates/{template_id}")
def update_template(template_id: int, payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        return {"success": False, "message": "Template not found"}
    for key in ["name", "description", "version", "sections"]:
        if key in payload:
            setattr(template, key, payload[key])
    db.commit()
    db.refresh(template)
    log_action(db, user, "updated template", "template", template.id, template.name)
    return {"success": True, "data": {"id": template.id, "name": template.name}}

@router.delete("/admin/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        return {"success": False, "message": "Template not found"}
    db.delete(template)
    db.commit()
    log_action(db, user, "deleted template", "template", template_id)
    return {"success": True, "message": "Template deleted"}

# ============ CA LIBRARY ============
@router.get("/admin/ca-library")
def list_ca(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.query(CALibrary).all()
    return {"success": True, "data": [
        {
            "id": c.id, "title": c.title, "description": c.description,
            "category": c.category, "severity": c.severity,
        } for c in items
    ]}

@router.post("/admin/ca-library")
def create_ca(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ca = CALibrary(
        title=payload.get("title"),
        description=payload.get("description"),
        category=payload.get("category"),
        severity=payload.get("severity"),
    )
    db.add(ca)
    db.commit()
    db.refresh(ca)
    log_action(db, user, "created CA", "ca_library", ca.id, ca.title)
    return {"success": True, "data": {
        "id": ca.id, "title": ca.title, "description": ca.description,
        "category": ca.category, "severity": ca.severity,
    }}

@router.patch("/admin/ca-library/{ca_id}")
def update_ca(ca_id: int, payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ca = db.query(CALibrary).filter(CALibrary.id == ca_id).first()
    if not ca:
        return {"success": False, "message": "CA not found"}
    for key in ["title", "description", "category", "severity"]:
        if key in payload:
            setattr(ca, key, payload[key])
    db.commit()
    return {"success": True, "data": {"id": ca.id, "title": ca.title}}

@router.delete("/admin/ca-library/{ca_id}")
def delete_ca(ca_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ca = db.query(CALibrary).filter(CALibrary.id == ca_id).first()
    if not ca:
        return {"success": False, "message": "CA not found"}
    db.delete(ca)
    db.commit()
    return {"success": True, "message": "CA deleted"}

# ============ INSPECTORS ============
@router.get("/auth/inspectors")
def list_inspectors(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inspectors = db.query(User).filter(User.role == UserRole.inspector).all()
    return {"success": True, "data": [
        {"id": i.id, "name": i.name, "email": i.email, "role": i.role.value} for i in inspectors
    ]}

@router.post("/auth/inspectors")
def create_inspector(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    existing = db.query(User).filter(User.email == payload.get("email")).first()
    if existing:
        return {"success": False, "message": "Email already registered"}
    inspector = User(
        email=payload.get("email"),
        hashed_password=hash_password(payload.get("password")),
        name=payload.get("name"),
        role=UserRole.inspector,
    )
    db.add(inspector)
    db.commit()
    db.refresh(inspector)
    log_action(db, user, "created inspector", "user", inspector.id, inspector.name)
    return {"success": True, "data": {
        "id": inspector.id, "name": inspector.name,
        "email": inspector.email, "role": inspector.role.value,
    }}

@router.delete("/auth/inspectors/{inspector_id}")
def delete_inspector(inspector_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inspector = db.query(User).filter(User.id == inspector_id, User.role == UserRole.inspector).first()
    if not inspector:
        return {"success": False, "message": "Inspector not found"}
    db.delete(inspector)
    db.commit()
    log_action(db, user, "deleted inspector", "user", inspector_id)
    return {"success": True, "message": "Inspector deleted"}

# ============ ASSIGNMENTS ============
@router.get("/admin/assignments")
def list_assignments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assignments = db.query(Assignment).all()
    result = []
    for a in assignments:
        vessel = db.query(Vessel).filter(Vessel.id == a.vessel_id).first()
        inspector = db.query(User).filter(User.id == a.inspector_id).first()
        template = db.query(Template).filter(Template.id == a.template_id).first() if a.template_id else None
        result.append({
            "id": a.id, "vessel_id": a.vessel_id,
            "vessel": vessel.name if vessel else None,
            "template_id": a.template_id,
            "template": template.name if template else None,
            "inspector_id": a.inspector_id,
            "inspector": inspector.name if inspector else None,
            "due_date": a.due_date.isoformat() if a.due_date else None,
            "status": a.status.value, "notes": a.notes,
        })
    return {"success": True, "data": result}

@router.post("/admin/assignments")
def create_assignment(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    due_date = None
    if payload.get("due_date"):
        try:
            due_date = datetime.fromisoformat(payload["due_date"])
        except (ValueError, TypeError):
            due_date = None
    template_id = payload.get("template_id")
    tv = payload.get("template_version_id")
    if not template_id and tv:
        t = db.query(Template).filter(Template.name == str(tv)).first()
        if t:
            template_id = t.id
    assignment = Assignment(
        vessel_id=payload.get("vessel_id"),
        template_id=template_id,
        inspector_id=payload.get("inspector_id"),
        due_date=due_date,
        notes=payload.get("notes"),
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    log_action(db, user, "created assignment", "assignment", assignment.id)
    return {"success": True, "data": {"id": assignment.id}}

@router.patch("/admin/assignments/{assignment_id}")
def update_assignment(assignment_id: int, payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        return {"success": False, "message": "Assignment not found"}
    if "status" in payload:
        a.status = payload["status"]
    if "notes" in payload:
        a.notes = payload["notes"]
    if "due_date" in payload and payload["due_date"]:
        try:
            a.due_date = datetime.fromisoformat(payload["due_date"])
        except (ValueError, TypeError):
            pass
    db.commit()
    return {"success": True, "data": {"id": a.id, "status": a.status.value}}

@router.delete("/admin/assignments/{assignment_id}")
def delete_assignment(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        return {"success": False, "message": "Assignment not found"}
    # Delete related records first (avoid foreign key errors)
    db.query(Report).filter(Report.assignment_id == assignment_id).delete()
    db.query(Inspection).filter(Inspection.assignment_id == assignment_id).delete()
    db.query(InspectionSession).filter(InspectionSession.assignment_id == assignment_id).delete()
    db.delete(a)
    db.commit()
    log_action(db, user, "deleted assignment", "assignment", assignment_id)
    return {"success": True, "message": "Assignment deleted"}

def _resolve_template(db, assignment):
    if not assignment or not assignment.template_id:
        return None
    tid = assignment.template_id
    try:
        t = db.query(Template).filter(Template.id == int(tid)).first()
        if t:
            return t.name
    except (ValueError, TypeError):
        pass
    t = db.query(Template).filter(Template.name == str(tid)).first()
    if t:
        return t.name
    return str(tid)


def _resolve_fleet(db, vessel):
    """Fleet may be stored as numeric id or as a name string. Handle both."""
    if not vessel or not vessel.fleet_id:
        return None
    fid = vessel.fleet_id
    try:
        f = db.query(Fleet).filter(Fleet.id == int(fid)).first()
        if f:
            return f.name
    except (ValueError, TypeError):
        pass
    f = db.query(Fleet).filter(Fleet.name == str(fid)).first()
    if f:
        return f.name
    return str(fid)


# ============ SESSIONS ============
@router.get("/admin/sessions")
def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sessions = db.query(InspectionSession).all()
    result = []
    for s in sessions:
        inspector = db.query(User).filter(User.id == s.inspector_id).first()
        assignment = db.query(Assignment).filter(Assignment.id == s.assignment_id).first()
        vessel = db.query(Vessel).filter(Vessel.id == assignment.vessel_id).first() if assignment else None
        fleet = _resolve_fleet(db, vessel)
        template = _resolve_template(db, assignment)
        result.append({
            "id": s.id, "assignment_id": s.assignment_id,
            "inspector": inspector.name if inspector else None,
            "vessel": vessel.name if vessel else None,
            "fleet": fleet if fleet else None,
            "template": template if template else None,
            "status": s.status,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        })
    return {"success": True, "data": result}

@router.get("/admin/sessions/{session_id}/detail")
def session_detail(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = db.query(InspectionSession).filter(InspectionSession.id == session_id).first()
    if not session:
        return {"success": False, "message": "Session not found"}
    inspection = db.query(Inspection).filter(Inspection.assignment_id == session.assignment_id).first()
    answers = inspection.answers if inspection and inspection.answers else {}
    questions = []
    evidence = []
    for qid, val in answers.items():
        if qid == "__cover_image__":
            continue
        if not isinstance(val, dict):
            continue
        q_text = val.get("question_text", qid)
        ans = val.get("answer")
        comment = val.get("comment", "")
        questions.append({
            "id": qid,
            "question": q_text,
            "answer": ans,
            "comment": comment,
            "is_finding": ans == "no",
        })
        # collect photos as evidence
        photos = val.get("photos", [])
        for i, p in enumerate(photos):
            evidence.append({"question_id": qid, "question": q_text, "url": p})
    return {"success": True, "data": {
        "session_id": session.id,
        "status": session.status,
        "questions": questions,
        "evidence": evidence,
        "total_questions": len(questions),
        "findings": len([q for q in questions if q["is_finding"]]),
    }}

# ============ REPORTS / REVIEW QUEUE ============
@router.get("/admin/reports")
def list_reports(status: str = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Report)
    if status:
        query = query.filter(Report.status == status)
    reports = query.all()
    result = []
    for r in reports:
        assignment = db.query(Assignment).filter(Assignment.id == r.assignment_id).first()
        vessel = db.query(Vessel).filter(Vessel.id == assignment.vessel_id).first() if assignment else None
        inspector = db.query(User).filter(User.id == assignment.inspector_id).first() if assignment else None
        template = _resolve_template(db, assignment)
        fleet = _resolve_fleet(db, vessel)
        result.append({
            "id": r.id, "inspection_id": r.inspection_id, "assignment_id": r.assignment_id,
            "vessel": vessel.name if vessel else None,
            "fleet": fleet if fleet else None,
            "template": template if template else None,
            "inspector": inspector.name if inspector else None,
            "status": r.status, "findings_count": r.findings_count,
            "score": r.score, "review_notes": r.review_notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"success": True, "data": result}

@router.patch("/admin/reports/{report_id}/review")
def review_report(report_id: int, payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        return {"success": False, "message": "Report not found"}
    report.status = payload.get("status", "approved")
    report.review_notes = payload.get("notes")
    report.reviewed_by = user.id
    report.reviewed_at = datetime.utcnow()
    db.commit()
    log_action(db, user, f"reviewed report ({report.status})", "report", report.id)
    return {"success": True, "data": {"id": report.id, "status": report.status}}

# ============ CAPA TRACKER ============
@router.get("/admin/capas")
def list_capas(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    capas = db.query(CAPA).all()
    result = []
    for c in capas:
        assignment = db.query(Assignment).filter(Assignment.id == c.assignment_id).first() if c.assignment_id else None
        vessel = db.query(Vessel).filter(Vessel.id == assignment.vessel_id).first() if assignment else None
        fleet = _resolve_fleet(db, vessel)
        inspector = db.query(User).filter(User.id == assignment.inspector_id).first() if assignment else None
        session = db.query(InspectionSession).filter(InspectionSession.assignment_id == c.assignment_id).first() if c.assignment_id else None
        result.append({
            "id": c.id, "report_id": c.report_id, "assignment_id": c.assignment_id,
            "question_text": c.question_text, "finding": c.finding,
            "corrective_action": c.corrective_action, "status": c.status,
            "vessel": vessel.name if vessel else None,
            "fleet": fleet if fleet else None,
            "severity": "Medium",
            "session_id": session.id if session else None,
            "assignee": inspector.name if inspector else None,
            "due_date": c.due_date.isoformat() if c.due_date else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return {"success": True, "data": result}

@router.post("/admin/capas")
def create_capa(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    due_date = None
    if payload.get("due_date"):
        try:
            due_date = datetime.fromisoformat(payload["due_date"])
        except (ValueError, TypeError):
            pass
    capa = CAPA(
        report_id=payload.get("report_id"),
        assignment_id=payload.get("assignment_id"),
        question_text=payload.get("question_text"),
        finding=payload.get("finding"),
        corrective_action=payload.get("corrective_action"),
        due_date=due_date,
    )
    db.add(capa)
    db.commit()
    db.refresh(capa)
    log_action(db, user, "created CAPA", "capa", capa.id)
    return {"success": True, "data": {"id": capa.id}}

@router.patch("/admin/capas/{capa_id}")
def update_capa(capa_id: int, payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    capa = db.query(CAPA).filter(CAPA.id == capa_id).first()
    if not capa:
        return {"success": False, "message": "CAPA not found"}
    if "status" in payload:
        capa.status = payload["status"]
        if payload["status"] == "closed":
            capa.closed_at = datetime.utcnow()
    if "corrective_action" in payload:
        capa.corrective_action = payload["corrective_action"]
    db.commit()
    log_action(db, user, f"updated CAPA ({capa.status})", "capa", capa.id)
    return {"success": True, "data": {"id": capa.id, "status": capa.status}}

# ============ AUDIT LOG ============
@router.get("/admin/audit-log")
def list_audit_log(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return {"success": True, "data": [
        {
            "id": l.id, "user_name": l.user_name, "action": l.action,
            "entity": l.entity, "entity_id": l.entity_id, "details": l.details,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        } for l in logs
    ]}

# ============ DASHBOARD STATS ============
@router.get("/admin/dashboard")
def dashboard_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"success": True, "data": {
        "total_vessels": db.query(Vessel).count(),
        "total_fleets": db.query(Fleet).count(),
        "total_inspectors": db.query(User).filter(User.role == UserRole.inspector).count(),
        "total_questions": db.query(QuestionBank).count(),
        "total_templates": db.query(Template).count(),
        "total_assignments": db.query(Assignment).count(),
        "active_sessions": db.query(InspectionSession).filter(InspectionSession.status == "active").count(),
        "pending_reviews": db.query(Report).filter(Report.status == "pending_review").count(),
        "open_capas": db.query(CAPA).filter(CAPA.status == "open").count(),
    }}

# ============ PROFILES (randomness, scoring, ai, report) ============
@router.get("/admin/profiles")
def list_profiles(kind: str = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Profile)
    if kind:
        query = query.filter(Profile.kind == kind)
    profiles = query.all()
    return {"success": True, "data": [
        {"id": p.id, "kind": p.kind, "name": p.name, "data": p.data or {}} for p in profiles
    ]}

@router.post("/admin/profiles")
def create_profile(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    profile = Profile(
        kind=payload.get("kind"),
        name=payload.get("name"),
        data=payload.get("data", {}),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    log_action(db, user, f"created {profile.kind} profile", "profile", profile.id, profile.name)
    return {"success": True, "data": {"id": profile.id, "kind": profile.kind, "name": profile.name}}

@router.patch("/admin/profiles/{profile_id}")
def update_profile(profile_id: int, payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        return {"success": False, "message": "Profile not found"}
    if "name" in payload:
        profile.name = payload["name"]
    if "data" in payload:
        profile.data = payload["data"]
    db.commit()
    return {"success": True, "data": {"id": profile.id, "name": profile.name}}

@router.delete("/admin/profiles/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        return {"success": False, "message": "Profile not found"}
    db.delete(profile)
    db.commit()
    log_action(db, user, "deleted profile", "profile", profile_id)
    return {"success": True, "message": "Profile deleted"}
    # ═══════════ ANALYTICS ═══════════
@router.get("/analytics")
def get_analytics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from ..models.vessel import Vessel
    from ..models.fleet import Fleet
    from ..models.template import Template
    
    total_vessels = db.query(Vessel).count()
    total_fleets = db.query(Fleet).count()
    total_templates = db.query(Template).count()
    total_assignments = db.query(Assignment).count()
    total_sessions = db.query(InspectionSession).count()
    total_reports = db.query(Report).count()
    total_capas = db.query(CAPA).count()
    
    # Assignments by status
    status_counts = {}
    for a in db.query(Assignment).all():
        s = a.status.value if hasattr(a.status, 'value') else str(a.status)
        status_counts[s] = status_counts.get(s, 0) + 1
    
    # CAPA by status
    capa_counts = {}
    for c in db.query(CAPA).all():
        capa_counts[c.status] = capa_counts.get(c.status, 0) + 1
    
    # Reports by status
    report_counts = {}
    for r in db.query(Report).all():
        report_counts[r.status] = report_counts.get(r.status, 0) + 1
    
    return {"success": True, "data": {
        "totals": {
            "vessels": total_vessels,
            "fleets": total_fleets,
            "templates": total_templates,
            "assignments": total_assignments,
            "sessions": total_sessions,
            "reports": total_reports,
            "capas": total_capas,
        },
        "assignments_by_status": status_counts,
        "capa_by_status": capa_counts,
        "reports_by_status": report_counts,
    }}
    # ═══════════ SETTINGS (generic key-value store) ═══════════
@router.get("/settings/{key}")
def get_setting(key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    profile = db.query(Profile).filter(Profile.kind == "settings", Profile.name == key).first()
    if not profile:
        return {"success": True, "data": None}
    return {"success": True, "data": profile.data}

@router.put("/settings/{key}")
def save_setting(key: str, payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    profile = db.query(Profile).filter(Profile.kind == "settings", Profile.name == key).first()
    if not profile:
        profile = Profile(kind="settings", name=key, data=payload)
        db.add(profile)
    else:
        profile.data = payload
    db.commit()
    log_action(db, user, f"updated {key} settings", "settings", None)
    return {"success": True, "data": payload}