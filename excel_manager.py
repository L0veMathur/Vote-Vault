# excel_manager.py
import pandas as pd
from datetime import datetime
import os

class ExcelManager:
    def __init__(self, input_excel, output_excel):
        self.input_excel = input_excel
        self.output_excel = output_excel
        self.voter_db = None
    
    def load_voter_registry(self):
        """
        Load existing voter database from Excel
        Expected columns: VoterID, Name, DOB, Email, Phone, Address
        """
        try:
            self.voter_db = pd.read_excel(self.input_excel)
            required_cols = ['VoterID', 'Name', 'DOB', 'Email']
            
            if not all(col in self.voter_db.columns for col in required_cols):
                raise ValueError(f"Excel must contain columns: {required_cols}")
            
            # Add HasVoted column if not exists
            if 'HasVoted' not in self.voter_db.columns:
                self.voter_db['HasVoted'] = False
            
            return True, len(self.voter_db)
        except Exception as e:
            return False, str(e)
    
    def export_vote_log(self, vote_records):
        """
        Export comprehensive vote log to Excel
        vote_records format: list of dicts with:
        - Name, VoterID, Vote, Timestamp, Geolocation, KYCImageHash
        """
        df = pd.DataFrame(vote_records)
        
        # Reorder columns for clarity
        column_order = [
            'Timestamp',
            'VoterID',
            'Name',
            'Vote',
            'GeolocationCity',
            'GeolocationCountry',
            'KYCImageHash',
            'BlockHash',
            'VoteHash'
        ]
        
        df = df[column_order]
        
        # Format timestamp
        df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.strftime(
            '%Y-%m-%d %H:%M:%S'
        )
        
        # Create Excel writer with formatting
        with pd.ExcelWriter(self.output_excel, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Vote Log', index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Vote Log']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(cell.value)
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        return True
    
    def mark_voter_as_voted(self, voter_id):
        """Update voter registry to prevent duplicate votes"""
        self.voter_db.loc[
            self.voter_db['VoterID'] == voter_id, 
            'HasVoted'
        ] = True
        
        # Save updated registry
        self.voter_db.to_excel(self.input_excel, index=False)