from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PersonalInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str | None = Field(default=None, max_length=255)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=50)


class ClinicalInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    current_occupation: str | None = Field(default=None, max_length=255)
    highest_education_level: str | None = Field(default=None, max_length=255)
    primary_concerns: str | None = Field(default=None, max_length=2000)
    symptom_onset_age: int | None = Field(default=None, ge=0)


class MedicalInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    relevant_history: str | None = Field(default=None, max_length=2000)
    current_medications: str | None = Field(default=None, max_length=2000)
    family_history: str | None = Field(default=None, max_length=2000)
    sleep_patterns: str | None = Field(default=None, max_length=2000)


class UserBase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    personal_info: PersonalInfo | None = None
    clinical_info: ClinicalInfo | None = None
    medical_info: MedicalInfo | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    personal_info: PersonalInfo | None = None
    clinical_info: ClinicalInfo | None = None
    medical_info: MedicalInfo | None = None
