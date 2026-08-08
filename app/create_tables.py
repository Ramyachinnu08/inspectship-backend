from app.core.database import engine, Base
from app.models import user, vessel, template, assignment, inspection, fleet, question, ca_library, session, report, capa, audit_log, profile

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("All tables created successfully!")