import uuid

def generate_id(prefix=""):
    """Generates a unique 8-character hex ID with an optional prefix."""
    return f"{prefix}{uuid.uuid4().hex[:8]}"
