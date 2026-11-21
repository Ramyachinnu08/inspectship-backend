from fastapi import APIRouter, Depends, Body, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime
from ..core.database import get_db
from ..models.user import User, UserRole
from ..models.vessel import Vessel
from ..models.template import Template
from ..models.assignment import Assignment, AssignmentStatus
from ..models.session import InspectionSession
from ..models.inspection import Inspection
from ..models.report import Report
from ..models.capa import CAPA
from ..models.question import QuestionBank
from ..models.audit_log import AuditLog
from .auth import get_current_user

router = APIRouter(prefix="/api/inspector", tags=["Inspector"])

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

# ═══════════ MY ASSIGNMENTS ═══════════
@router.get("/assignments")
def my_assignments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assigns = db.query(Assignment).filter(Assignment.inspector_id == user.id).all()
    result = []
    for a in assigns:
        vessel = db.query(Vessel).filter(Vessel.id == a.vessel_id).first()
        template = db.query(Template).filter(Template.id == a.template_id).first() if a.template_id else None
        # Check if session exists
        session = db.query(InspectionSession).filter(InspectionSession.assignment_id == a.id).first()
        result.append({
            "id": a.id,
            "vessel_id": a.vessel_id,
            "vessel": vessel.name if vessel else "Unknown",
            "vessel_imo": vessel.imo if vessel else "",
            "template_id": a.template_id,
            "template": template.name if template else "No template",
            "template_sections": template.sections if template else [],
            "due_date": a.due_date.isoformat() if a.due_date else None,
            "status": a.status.value,
            "notes": a.notes,
            "has_session": session is not None,
            "session_id": session.id if session else None,
            "session_status": session.status if session else None,
        })
    return {"success": True, "data": result}

# ═══════════ START / RESUME SESSION ═══════════
@router.post("/assignments/{assignment_id}/start")
def start_or_resume(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id,
        Assignment.inspector_id == user.id
    ).first()
    if not assignment:
        return {"success": False, "message": "Assignment not found"}
    # Check for existing session
    session = db.query(InspectionSession).filter(InspectionSession.assignment_id == assignment_id).first()
    if not session:
        session = InspectionSession(
            assignment_id=assignment_id,
            inspector_id=user.id,
            status="active",
        )
        db.add(session)
        # Update assignment status to in_progress
        assignment.status = AssignmentStatus.in_progress
        db.commit()
        db.refresh(session)
        log_action(db, user, "started inspection", "session", session.id)
    else:
        session.status = "active"
        session.last_activity = datetime.utcnow()
        db.commit()
        db.refresh(session)
    # Load or create inspection record
    inspection = db.query(Inspection).filter(Inspection.assignment_id == assignment_id).first()
    if not inspection:
        inspection = Inspection(assignment_id=assignment_id, answers={})
        db.add(inspection)
        db.commit()
        db.refresh(inspection)
    return {"success": True, "data": {
        "session_id": session.id,
        "inspection_id": inspection.id,
        "answers": inspection.answers or {},
    }}

# ═══════════ SAVE ANSWERS (draft) ═══════════
@router.patch("/inspections/{inspection_id}")
def save_answers(inspection_id: int, payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        return {"success": False, "message": "Inspection not found"}
    if payload.get("answers") is not None:
        inspection.answers = payload["answers"]
    if payload.get("master_name") is not None:
        inspection.master_name = payload["master_name"]
    if payload.get("master_email") is not None:
        inspection.master_email = payload["master_email"]
    if payload.get("master_signature_url") is not None:
        inspection.master_signature_url = payload["master_signature_url"]
    if payload.get("inspector_signature_url") is not None:
        inspection.inspector_signature_url = payload["inspector_signature_url"]
    db.commit()
    return {"success": True, "data": {"id": inspection.id}}

# ═══════════ SUBMIT INSPECTION ═══════════
@router.post("/inspections/{inspection_id}/submit")
def submit_inspection(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        return {"success": False, "message": "Inspection not found"}
    inspection.submitted_at = datetime.utcnow()
    # Update assignment status
    assignment = db.query(Assignment).filter(Assignment.id == inspection.assignment_id).first()
    if assignment:
        assignment.status = AssignmentStatus.submitted
    # Update session
    session = db.query(InspectionSession).filter(InspectionSession.assignment_id == inspection.assignment_id).first()
    if session:
        session.status = "completed"
        session.completed_at = datetime.utcnow()
    # Count findings (No answers)
    findings = 0
    answers = inspection.answers or {}
    for qid, val in answers.items():
        if isinstance(val, dict) and val.get("answer") == "no":
            findings += 1
    # Create report for admin review
    report = Report(
        inspection_id=inspection.id,
        assignment_id=inspection.assignment_id,
        status="approved",
        findings_count=findings,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    # Auto-create CAPAs for each finding
    for qid, val in answers.items():
        if isinstance(val, dict) and val.get("answer") == "no":
            capa = CAPA(
                report_id=report.id,
                assignment_id=inspection.assignment_id,
                question_text=val.get("question_text", ""),
                finding=val.get("comment", "Finding recorded"),
                status="open",
            )
            db.add(capa)
    db.commit()
    log_action(db, user, "submitted inspection", "inspection", inspection.id)
    return {"success": True, "data": {"report_id": report.id, "findings": findings}}
    # ═══════════ GET INSPECTION DETAILS (for report viewer) ═══════════
@router.get("/assignments/{assignment_id}/inspection")
def get_inspection_detail(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id,
        Assignment.inspector_id == user.id
    ).first()
    if not assignment:
        return {"success": False, "message": "Assignment not found"}
    inspection = db.query(Inspection).filter(Inspection.assignment_id == assignment_id).first()
    if not inspection:
        return {"success": False, "message": "No inspection found"}
    vessel = db.query(Vessel).filter(Vessel.id == assignment.vessel_id).first()
    template = db.query(Template).filter(Template.id == assignment.template_id).first() if assignment.template_id else None
    # Count findings
    answers = inspection.answers or {}
    findings = 0
    for qid, val in answers.items():
        if isinstance(val, dict) and val.get("answer") == "no":
            findings += 1
    return {"success": True, "data": {
        "assignment_id": assignment.id,
        "vessel": vessel.name if vessel else "Unknown",
        "vessel_imo": vessel.imo if vessel else "",
        "template": template.name if template else "",
        "status": assignment.status.value,
        "answers": answers,
        "findings": findings,
        "master_name": inspection.master_name,
        "submitted_at": inspection.submitted_at.isoformat() if inspection.submitted_at else None,
    }}


@router.post("/inspections/{inspection_id}/email-report")
async def email_report(inspection_id: int, file: UploadFile = File(...), findings: str = Form("0"),
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Email the app-generated PDF report to the admin and the vessel Master."""
    from ..core.email_utils import send_email, report_submitted_html, is_configured, ADMIN_EMAIL
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        return {"success": False, "message": "Inspection not found"}
    if not is_configured():
        return {"success": False, "message": "Email not configured on server (SMTP_USER / SMTP_PASSWORD)"}
    assignment = db.query(Assignment).filter(Assignment.id == inspection.assignment_id).first()
    vessel = db.query(Vessel).filter(Vessel.id == assignment.vessel_id).first() if assignment else None

    recipients = []
    if ADMIN_EMAIL:
        recipients += [e.strip() for e in ADMIN_EMAIL.split(",") if e.strip()]
    else:
        admins = db.query(User).filter(User.role.in_([UserRole.admin, UserRole.super_admin])).all()
        recipients += [a.email for a in admins if a.email]
    if inspection.master_email:
        recipients.append(inspection.master_email.strip())
    recipients = list(dict.fromkeys([r for r in recipients if r]))
    if not recipients:
        return {"success": False, "message": "No recipient email (set ADMIN_EMAIL or Master email)"}

    pdf_bytes = await file.read()
    vname = vessel.name if vessel else "Vessel"
    fname = file.filename or f"{vname.replace(' ', '_')}_Inspection_Report.pdf"
    when = (inspection.submitted_at or datetime.utcnow()).strftime("%d/%m/%Y")
    html = report_submitted_html(vname, vessel.imo if vessel else "", getattr(assignment, "port", None),
                                 user.name, when, findings, getattr(inspection, "master_name", None))
    sent = send_email(recipients, f"Inspection report - {vname} - {when}", html, [(fname, pdf_bytes, "pdf")])
    log_action(db, user, "emailed report", "inspection", inspection_id, details=", ".join(recipients))
    return {"success": sent, "recipients": recipients,
            "message": "Report emailed" if sent else "Email sending failed - check server SMTP settings"}