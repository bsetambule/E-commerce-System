from datetime import datetime, timezone, timedelta
from app.extensions import db
from flask_login import UserMixin
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

class User(UserMixin, db.Model):
    __tablename__ = "users"
    # -----------------------------
    # CORE IDENTITY
    # -----------------------------
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), unique=True, index=True)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc), index=True)
    # -----------------------------
    # ACCOUNT STATE
    # -----------------------------
    is_active = db.Column(db.Boolean, default=True)
    is_frozen = db.Column(db.Boolean, default=False)
    is_flagged = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    # -----------------------------
    # SECURITY STATE
    # -----------------------------
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    # -----------------------------
    # RELATIONSHIPS
    # -----------------------------
    roles = db.relationship("Role", secondary="user_roles", back_populates="users")
    branch_staff = db.relationship("BranchStaff", back_populates="user", cascade="all, delete-orphan")
    customer_profile = db.relationship("CustomerProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")
    courier_profile = db.relationship("CourierProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")
    cart = db.relationship("Cart", back_populates="user", uselist=False, cascade="all, delete-orphan")
    staff_profile = db.relationship("StaffProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")
    # -----------------------------
    # ROLE CORE (OPTIMIZED)
    # -----------------------------
    def role_names(self):
        return {r.name for r in self.roles}

    def has_role(self, role_name: str) -> bool:
        return role_name in self.role_names()

    def has_any_role(self, *role_names) -> bool:
        return bool(self.role_names().intersection(role_names))
    # -----------------------------
    # BRANCH LOGIC
    # -----------------------------
    def get_branches(self):
        return [bs.branch for bs in self.branch_staff]

    def is_staff_in_branch(self, branch_id: int) -> bool:
        return any(bs.branch_id == branch_id for bs in self.branch_staff)
    # -----------------------------
    # PASSWORD HANDLING
    # -----------------------------
    @property
    def password(self):
        raise AttributeError("Password is not readable")

    @password.setter
    def password(self, raw_password: str):
        self.password_hash = ph.hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        try:
            return ph.verify(self.password_hash, raw_password)
        except VerifyMismatchError:
            return False
        except Exception:
            return False
    # -----------------------------
    # SECURITY: LOCKING SYSTEM
    # -----------------------------
    @property
    def is_locked(self) -> bool:
        if not self.locked_until:
            return False
        now = datetime.now(timezone.utc)
        locked_until = self.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        return locked_until > now

    def lock(self, minutes: int = 30):
        self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        self.failed_attempts = 0

    def register_failed_login(self):
        self.failed_attempts = min(self.failed_attempts + 1, 5)
        if self.failed_attempts >= 5:
            self.lock()

    def reset_security_state(self):
        self.failed_attempts = 0
        self.locked_until = None
    # -----------------------------
    # LOGIN SUCCESS HOOK (IMPORTANT ADDITION)
    # -----------------------------
    def on_successful_login(self):
        self.reset_security_state()
    # -----------------------------
    # CENTRAL ACCESS CHECK
    # -----------------------------
    def can_login(self) -> bool:
    # -----------------------------
    # BASIC ACCOUNT CHECKS
    # -----------------------------
        if not self.is_active:
            return False

        if self.is_frozen:
            return False

        if self.is_locked:
            return False

        if self.is_deleted:
            return False
    # -----------------------------
    # STORE ACCESS CONTROL
    # -----------------------------
        if self.has_any_role("STAFF", "STOREMANAGER", "INVENTORYMANAGER", "DELIVERYMANAGER", "COURIER"):
            for bs in self.branch_staff:
                if not bs.branch or not bs.branch.is_active:
                    return False
        return True
    def full_name(self):
        if self.customer_profile:
            return f"{self.customer_profile.first_name} {self.customer_profile.last_name}"
        return self.email
    