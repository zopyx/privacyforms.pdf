#!/usr/bin/env python3
"""Script to extract fields from FilledForm.pdf, generate sample data, and fill the form."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add the package to path if running from source
sys.path.insert(0, str(Path(__file__).parent))

from privacyforms_pdf import PDFFormExtractor


def generate_sample_value(field_type: str, field_name: str) -> str | bool:
    """Generate a sample value based on field type."""
    match field_type:
        case "checkbox":
            return True
        case "datefield":
            return "2026-03-07"
        case "radiobuttongroup":
            return "Option1"
        case _:  # textfield and others
            return f"Sample {field_name}"


def main() -> int:
    """Main entry point."""
    pdf_path = Path("samples/FilledForm.pdf")
    json_path = Path("data.json")
    output_path = Path("filled.pdf")

    if not pdf_path.exists():
        print(f"Error: {pdf_path} not found")
        return 1

    print(f"Step 1: Extracting fields from {pdf_path}...")
    extractor = PDFFormExtractor()

    # Check if PDF has a form
    if not extractor.has_form(pdf_path):
        print("Error: PDF does not contain a form")
        return 1

    # Extract form fields
    form_data = extractor.extract(pdf_path)
    print(f"Found {len(form_data.fields)} field(s)")

    # Display extracted fields
    print("\n--- Extracted Fields ---")
    for field in form_data.fields:
        print(f"  - {field.name} (type: {field.field_type})")

    # Generate sample data
    print(f"\nStep 2: Generating {json_path}...")
    sample_data: dict[str, str | bool] = {}
    for field in form_data.fields:
        sample_data[field.name] = generate_sample_value(field.field_type, field.name)

    # Write JSON file
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sample_data, f, indent=2, ensure_ascii=False)
    print(f"Sample data written to {json_path}")
    print(f"\n--- Sample Data ---")
    print(json.dumps(sample_data, indent=2))

    # Fill the form
    print(f"\nStep 3: Filling form and saving to {output_path}...")
    try:
        result = extractor.fill_form_from_json(
            pdf_path,
            json_path,
            output_path,
            validate=False,  # Skip validation to allow partial fills
        )
        print(f"Success! Filled PDF saved to: {result}")

        # Verify by extracting again
        print("\nStep 4: Verifying filled data...")
        filled_data = extractor.extract(result)
        print(f"Verified {len(filled_data.fields)} field(s) in output PDF")
        print("\n--- Filled Values ---")
        for field in filled_data.fields:
            print(f"  - {field.name}: {field.value!r}")

        return 0

    except Exception as e:
        print(f"Error filling form: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
