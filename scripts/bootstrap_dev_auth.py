# scripts/bootstrap_dev_auth.py
import uuid
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models.user import User
from app.models.tenant import Tenant
from app.auth.passwords import hash_password  # <- gebruikt jouw passlib context

TENANT_ID = "dev-tenant"
TENANT_NAME = "Dev Tenant"

EMAIL = "dev@inversiq.local"
PASSWORD = "dev12345!"  # kies iets
TIMEZONE = "America/New_York"


def main():
    db = SessionLocal()
    try:
        # tenant
        tenant = db.query(Tenant).filter(Tenant.id == TENANT_ID).first()
        if not tenant:
            tenant = Tenant(
                id=TENANT_ID,
                name=TENANT_NAME,
                slug=TENANT_ID,
                enabled_verticals=["construction"],
            )
            db.add(tenant)
            db.commit()
            print("✅ tenant created:", TENANT_ID)
        else:
            changed = False
            if not tenant.slug:
                tenant.slug = TENANT_ID
                changed = True
                print("✅ tenant slug set:", tenant.slug)
            if tenant.enabled_verticals is None:
                tenant.enabled_verticals = ["construction"]
                changed = True
                print("✅ tenant enabled_verticals set:", tenant.enabled_verticals)
            if changed:
                db.add(tenant)
                db.commit()

        # user
        user = db.query(User).filter(User.email == EMAIL).first()
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                tenant_id=TENANT_ID,
                email=EMAIL,
                password_hash=hash_password(PASSWORD),  # ✅ echte hash
                timezone=TIMEZONE,
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            db.add(user)
            db.commit()
            print("✅ user created:", EMAIL)
        else:
            # reset password (handig na db resets)
            user.password_hash = hash_password(PASSWORD)
            user.timezone = TIMEZONE
            user.is_active = True
            db.add(user)
            db.commit()
            print("✅ user updated/reset password:", EMAIL)

        print("\nLOGIN MET:")
        print("email:", EMAIL)
        print("password:", PASSWORD)
        print("tenant_id:", TENANT_ID)
        print("timezone:", TIMEZONE)

    finally:
        db.close()


if __name__ == "__main__":
    main()
