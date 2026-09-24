
def get_user_initials(user):
    if not user or not hasattr(user, "customer_profile") or not user.customer_profile:
        return "?"

    first = user.customer_profile.first_name[:1].upper()
    last = user.customer_profile.last_name[:1].upper()

    return f"{first}{last}"