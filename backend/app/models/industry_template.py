"""
models/industry_template.py

WHAT THIS FILE DOES:
Defines the `IndustryTemplate` table. This is what lets ONE platform
support clinics, restaurants, hotels, real estate, gyms, salons, law
firms, e-commerce, HR, and cold-calling WITHOUT writing separate code for
each one. Each row is one industry with:

  - A base prompt template (with placeholders like {company_name})
  - A list of default actions available to that industry
  - A list of suggested knowledge base categories (menu, price list, etc.)

These rows are seeded once (see templates/industry_templates.py for the
seed data) and read by the prompt_builder service whenever a user creates
a new agent and picks an industry from a dropdown.

Adding a new industry to the platform = adding one new row to this table.
No new code, no redeploy needed.
"""

import uuid
from sqlalchemy import Column, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class IndustryTemplate(Base):
    __tablename__ = "industry_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String, unique=True, nullable=False)          # "clinic", "restaurant", "cold_caller", etc.
    display_name = Column(String, nullable=False)               # "Clinic", "Restaurant"
    description = Column(String, nullable=True)

    base_prompt_template = Column(Text, nullable=False)         # uses {company_name}, {business_hours}, etc.
    default_actions = Column(JSON, default=list)                # ["book_appointment", "cancel_appointment"]
    suggested_kb_categories = Column(JSON, default=list)        # ["insurance_policies", "doctor_availability"]
    default_greeting_template = Column(Text, nullable=True)
