import pandas as pd
from datetime import datetime

# Create sample voter registry data
voter_data = {
    'VoterID': ['V001', 'V002', 'V003', 'V004', 'V005'],
    'Name': ['John Doe', 'Jane Smith', 'Bob Johnson', 'Alice Brown', 'Charlie Wilson'],
    'DOB': ['1990-01-15', '1985-05-20', '1992-03-10', '1988-11-30', '1995-07-25'],
    'Email': ['john.doe@example.com', 'jane.smith@example.com', 'bob.johnson@example.com', 
              'alice.brown@example.com', 'charlie.wilson@example.com'],
    'Phone': ['+1-555-0001', '+1-555-0002', '+1-555-0003', '+1-555-0004', '+1-555-0005'],
    'Address': ['123 Main St', '456 Oak Ave', '789 Pine Rd', '321 Elm St', '654 Maple Dr'],
    'HasVoted': [False, False, False, False, False]
}

# Create DataFrame
df = pd.DataFrame(voter_data)

# Save to Excel file
df.to_excel('voter_registry.xlsx', index=False, engine='openpyxl')

print("voter_registry.xlsx created successfully!")
print(f"Total voters registered: {len(df)}")
print("\nSample voter credentials for testing:")
for i in range(min(3, len(df))):
    print(f"  VoterID: {df.iloc[i]['VoterID']}, DOB: {df.iloc[i]['DOB']}, Email: {df.iloc[i]['Email']}")
