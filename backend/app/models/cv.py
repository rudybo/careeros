from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.core.database import Base


class CV(Base):
    __tablename__ = "cvs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    status: Mapped[str] = mapped_column(String(50), default="uploaded")
    kind: Mapped[str] = mapped_column(String(20), default="altro", server_default="altro")
    is_base: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    file_content: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    file_mime: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def has_file(self) -> bool:
        return self.file_size is not None and self.file_size > 0
