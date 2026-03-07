#!/bin/bash
# Demo script to extract fields from FilledForm.pdf, generate random realistic data.json, and fill the form

set -e

PDF_FILE="samples/FilledForm.pdf"
JSON_FILE="data.json"
OUTPUT_FILE="filled.pdf"

echo "=== PDF Form Fill Demo (Random Data) ==="
echo ""

# Check if PDF exists
if [ ! -f "$PDF_FILE" ]; then
    echo "Error: $PDF_FILE not found"
    exit 1
fi

# Step 1: List fields in the PDF
echo "Step 1: Extracting fields from $PDF_FILE..."
pdf-forms list-fields "$PDF_FILE" > /tmp/fields.txt
echo "Found $(wc -l < /tmp/fields.txt) field(s)"
echo ""
echo "--- Extracted Fields (first 20) ---"
head -22 /tmp/fields.txt
echo "..."
echo ""

# Step 2: Generate random data.json
echo "Step 2: Generating random $JSON_FILE..."
pdf-forms extract "$PDF_FILE" > /tmp/extracted.json

python3 -c "
import json
import random
import string
from datetime import datetime, timedelta

# Sample data pools
FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Oliver', 'Isabella', 'Elijah', 'Sophia', 'James',
               'Mia', 'Benjamin', 'Charlotte', 'Lucas', 'Amelia', 'Henry', 'Harper', 'Alexander', 'Evelyn', 'Mason']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
              'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin']
STREETS = ['Oak', 'Maple', 'Cedar', 'Pine', 'Elm', 'Washington', 'Lake', 'Hill', 'Park', 'Main',
           'Broadway', 'Chestnut', 'Spruce', 'Willow', 'Birch', 'Sunset', 'River', 'Meadow', 'Forest', 'Highland']
STREET_TYPES = ['St', 'Ave', 'Rd', 'Blvd', 'Ln', 'Dr', 'Way', 'Ct', 'Pl', 'Circle']
CITIES = ['Springfield', 'Franklin', 'Greenville', 'Madison', 'Clayton', 'Georgetown', 'Salem', 'Fairview', 'Riverside', 'Brooklyn',
          'Clinton', 'Marion', 'Oxford', 'Auburn', 'Dayton', 'Lexington', 'Milford', 'Winchester', 'Burlington', 'Manchester']
STATES = ['IL', 'CA', 'NY', 'TX', 'FL', 'PA', 'OH', 'MI', 'GA', 'NC', 'NJ', 'VA', 'WA', 'AZ', 'MA']
COMPANIES = ['Acme Corp', 'TechStart Inc', 'Global Solutions', 'Blue Sky Enterprises', 'Summit Technologies',
             'Pioneer Systems', 'Innovate Labs', 'Velocity Partners', 'Nexus Industries', 'Quantum Dynamics']
POSITIONS = ['Software Engineer', 'Project Manager', 'Data Analyst', 'Marketing Specialist', 'HR Coordinator',
             'Sales Representative', 'Operations Manager', 'UX Designer', 'Product Manager', 'DevOps Engineer']
SCHOOLS = ['State University', 'Community College', 'Technical Institute', 'Liberal Arts College', 'Online Academy']
DEGREES = ['B.S. in Computer Science', 'B.A. in Business Administration', 'M.B.A.', 'Associate Degree', 
           'High School Diploma', 'Certificate in Web Development', 'B.S. in Marketing', 'B.A. in Psychology']
RELATIONSHIPS = ['Former Manager', 'Colleague', 'Professor', 'Mentor', 'Supervisor', 'Team Lead', 'Director']
SKILLS_LIST = [
    'Python, JavaScript, React, Node.js, SQL, AWS',
    'Project management, Agile, Scrum, Jira, Confluence',
    'Data analysis, Python, R, Tableau, Excel, Statistics',
    'Marketing strategy, SEO, SEM, Google Analytics, Content creation',
    'UI/UX design, Figma, Adobe Creative Suite, Prototyping, User research',
    'Java, Spring Boot, Microservices, Docker, Kubernetes',
    'Salesforce, CRM management, Lead generation, Cold calling, Negotiation'
]

def random_phone():
    return f'({random.randint(200, 999)}) {random.randint(200, 999)}-{random.randint(1000, 9999)}'

def random_date(start_year=2015, end_year=2026):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    days_between = (end - start).days
    random_days = random.randint(0, days_between)
    return (start + timedelta(days=random_days)).strftime('%Y-%m-%d')

def random_name():
    return f'{random.choice(LAST_NAMES)}, {random.choice(FIRST_NAMES)} {random.choice(string.ascii_uppercase)}.'

def random_street():
    return f'{random.randint(100, 9999)} {random.choice(STREETS)} {random.choice(STREET_TYPES)}'

def random_salary():
    return f'\${random.randint(40, 150)},{random.randint(0, 999):03d}/year'

with open('/tmp/extracted.json') as f:
    data = json.load(f)

sample_data = {}

# Generate a consistent person
full_name = random_name()
street = random_street()
city = random.choice(CITIES)
state = random.choice(STATES)
zip_code = f'{random.randint(10000, 99999)}'

for field in data['fields']:
    name = field['name']
    field_type = field['field_type']
    
    # Generate value based on field name patterns
    if field_type == 'checkbox':
        # Random boolean for checkboxes
        sample_data[name] = random.choice([True, False])
    
    elif 'phone' in name.lower() or 'Phone' in name:
        if 'home' in name.lower():
            sample_data[name] = random_phone()
        elif 'business' in name.lower() or 'work' in name.lower():
            sample_data[name] = random_phone()
        elif 'cell' in name.lower() or 'mobile' in name.lower():
            sample_data[name] = random_phone()
        else:
            sample_data[name] = random_phone()
    
    elif name == 'Candidate Name':
        sample_data[name] = full_name
    
    elif 'date' in name.lower():
        if 'start' in name.lower() and 'job' not in name.lower():
            sample_data[name] = random_date(2025, 2026)  # Future start date
        elif 'start' in name.lower():
            sample_data[name] = random_date(2020, 2023)  # Past job start
        elif 'end' in name.lower():
            sample_data[name] = random_date(2023, 2025)  # Past job end
        else:
            sample_data[name] = random_date(2024, 2026)
    
    elif 'street' in name.lower() or 'address' in name.lower():
        if 'school' in name.lower():
            sample_data[name] = f'{city}, {state}'
        else:
            sample_data[name] = street
    
    elif name.lower() == 'city':
        sample_data[name] = city
    
    elif name.lower() == 'state':
        sample_data[name] = state
    
    elif name.lower() == 'zip':
        sample_data[name] = zip_code
    
    elif 'salary' in name.lower():
        sample_data[name] = random_salary()
    
    elif 'school' in name.lower() and 'name' in name.lower():
        sample_data[name] = f'{city} {random.choice(SCHOOLS)}'
    
    elif 'degree' in name.lower():
        sample_data[name] = random.choice(DEGREES)
    
    elif 'skills' in name.lower() or 'special' in name.lower():
        sample_data[name] = random.choice(SKILLS_LIST)
    
    elif 'employer' in name.lower():
        sample_data[name] = random.choice(COMPANIES)
    
    elif 'position' in name.lower() or 'title' in name.lower():
        sample_data[name] = random.choice(POSITIONS)
    
    elif 'referent' in name.lower():
        if 'name' in name.lower():
            sample_data[name] = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
        elif 'relationship' in name.lower():
            sample_data[name] = random.choice(RELATIONSHIPS)
        elif 'address' in name.lower():
            sample_data[name] = f'{random.randint(100, 999)} {random.choice(STREETS)} {random.choice(STREET_TYPES)}, {city}, {state}'
        elif 'phone' in name.lower():
            sample_data[name] = random_phone()
        else:
            sample_data[name] = f'Reference {name}'
    
    elif 'job' in name.lower() and 'company' in name.lower():
        sample_data[name] = random.choice(COMPANIES)
    
    elif 'job' in name.lower() and 'title' in name.lower():
        sample_data[name] = random.choice(POSITIONS)
    
    elif 'duties' in name.lower():
        duties = [
            'Led cross-functional team of 8 developers to deliver product on time',
            'Managed client relationships and increased sales by 25%',
            'Developed and maintained REST APIs serving 1M+ requests daily',
            'Conducted user research and designed intuitive interfaces',
            'Analyzed large datasets to identify business opportunities'
        ]
        sample_data[name] = random.choice(duties)
    
    elif 'supervisor' in name.lower():
        sample_data[name] = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
    
    elif 'city' in name.lower() and 'job' in name.lower():
        sample_data[name] = f'{city}, {state}'
    
    elif 'felony' in name.lower() or 'conviction' in name.lower():
        sample_data[name] = 'N/A'
    
    elif 'signature' in name.lower():
        sample_data[name] = f'{full_name}'
    
    else:
        # Default random text
        sample_data[name] = f'{name} Data {random.randint(100, 999)}'

with open('$JSON_FILE', 'w') as f:
    json.dump(sample_data, f, indent=2)
    
print(f'Random sample data written to $JSON_FILE')
print(f'Generated data for: {full_name}')
"
echo ""
echo "--- Sample Data (first 30 lines) ---"
head -30 "$JSON_FILE"
echo "..."
echo ""

# Step 3: Fill the form
echo "Step 3: Filling form and saving to $OUTPUT_FILE..."
pdf-forms fill-form "$PDF_FILE" "$JSON_FILE" -o "$OUTPUT_FILE" --no-validate
echo "Success! Filled PDF saved to: $OUTPUT_FILE"
echo ""

# Step 4: Verify
echo "Step 4: Verifying filled data..."
pdf-forms list-fields "$OUTPUT_FILE" > /tmp/filled_fields.txt
echo "Verified $(grep -c 'textfield\|checkbox\|signature\|datefield' /tmp/filled_fields.txt || echo 0) field(s) in output PDF"
echo ""
echo "--- Filled Values (first 25 lines) ---"
head -27 /tmp/filled_fields.txt
echo "..."
echo ""

echo "=== Demo Complete ==="
echo ""
echo "Files created:"
echo "  - $JSON_FILE : Random form data (JSON)"
echo "  - $OUTPUT_FILE : Filled PDF output"
