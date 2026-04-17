from pydantic import BaseModel


class RowGroup(BaseModel):
    """Representation of list of PDF fields in one row"""

    fields: list[PDFField] = []
    page_index: int = 0


class PDFField(BaseModel):
    """Representation of PDF field"""

    id: str
    type: str
    visual_x: int | None = None
    visual_y: int | None = None
    visual_width: int | None = None
    visual_height: int | None = None

    default_value: object | None = None
    values: list[str] = []
    value_options: list[str] = []

    max_length: int | None = None
    textarea_rows: int | None = None
    textarea_cols: int | None = None
