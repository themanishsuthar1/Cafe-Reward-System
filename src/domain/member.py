import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from src.domain.tier import Tier

def normalize_phone(phone: str) -> str:
    """
    Normalizes phone numbers to standard format (digits only).
    E.g. '+1 (555) 123-4567' -> '15551234567' or '5551234567'.
    Strips non-digit characters except leading plus if desired, but digits-only is cleanest.
    """
    if not phone:
        raise ValueError("Phone number cannot be empty.")
    
    digits = re.sub(r'\D', '', phone)
    if not digits:
        raise ValueError(f"Invalid phone number: '{phone}' contains no digits.")
    return digits

@dataclass
class MemberDomain:
    id: str
    name: str
    phone: str
    tier: Tier
    join_date: datetime

    def __post_init__(self):
        self.phone = normalize_phone(self.phone)
