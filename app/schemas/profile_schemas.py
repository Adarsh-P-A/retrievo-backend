import re
from pydantic import BaseModel, field_validator


class PhoneSetPayload(BaseModel):
    phone: str

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Phone number must be a string")

        phone = v.strip()
        phone = re.sub(r"[ \-\(\)]", "", phone)

        # E.164: + followed by 8–15 digits
        if not re.fullmatch(r"\+[1-9]\d{7,14}", phone):
            raise ValueError(
                "Invalid phone number. Use format: +<countrycode><number>"
            )

        return phone