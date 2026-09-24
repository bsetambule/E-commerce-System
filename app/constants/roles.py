# app/constants/roles.py

# Roles admin is allowed to create
ALLOWED_ASSIGNABLE_ROLES = {
    "COURIER",
    "STAFF",
    "STOREMANAGER",
    "SYSTEMMANAGER",
    "DELIVERYMANAGER",
    "DELIVERYSUPERVISOR",
    "PRODUCTMANAGER"
}

# Roles that REQUIRE a branch
BRANCH_REQUIRED_ROLES = {
    "STAFF",
    "STOREMANAGER",
    "DELIVERYSUPERVISOR"
}

# Customer roles
CUSTOMER_ROLES = {"CUSTOMER"}

# Protected roles (cannot be modified)
PROTECTED_ROLES = {"ADMIN"}